# coding=utf-8
"""
This script is used to train the kbody network.
"""
from __future__ import print_function, absolute_import

import tensorflow as tf
import time
import kbody
from datetime import datetime
from tensorflow.python.client.timeline import Timeline
from os.path import join

__author__ = 'Xin Chen'
__email__ = "chenxin13@mails.tsinghua.edu.cn"


FLAGS = tf.app.flags.FLAGS

# Basic model parameters.
tf.app.flags.DEFINE_string('train_dir', './events',
                           """The directory for storing training files.""")
tf.app.flags.DEFINE_integer('max_steps', 10000,
                            """The maximum number of training steps.""")
tf.app.flags.DEFINE_integer('save_frequency', 20,
                            """The frequency, in number of global steps, that
                            the summaries are written to disk""")
tf.app.flags.DEFINE_integer('log_frequency', 100,
                            """The frequency, in number of global steps, that
                            the training progress wiil be logged.""")
tf.app.flags.DEFINE_boolean('log_device_placement', False,
                            """Whether to log device placement.""")
tf.app.flags.DEFINE_boolean('restart', True,
                            """Restore the latest checkpoint if possible.""")
tf.app.flags.DEFINE_boolean('timeline', False,
                            """Enable timeline profiling if True.""")


def train_model(*args):

  with tf.Graph().as_default():
    global_step = tf.contrib.framework.get_or_create_global_step()

    # Read dataset configurations
    settings = kbody.inputs_settings(train=True)
    offsets = settings["kbody_term_sizes"]

    # Remove all commas because tensorflow scope name can not contain such
    # characters.
    kbody_terms = [x.replace(",", "") for x in settings["kbody_terms"]]

    # Get features and energies.
    features, energies = kbody.inputs(train=True)

    # Set the scaling factor
    num_kernels = features.get_shape().as_list()[2] * len(offsets)
    scale = tf.constant(1.0 / num_kernels, dtype=tf.float32)

    # Build a Graph that computes the logits predictions from the
    # inference model.
    pred_energies = kbody.inference(
      features,
      offsets,
      kbody_terms=kbody_terms,
      verbose=True,
    )
    energies = tf.cast(energies, tf.float32)

    # Setup the loss function
    loss = kbody.get_total_loss(energies, pred_energies)

    # Build a Graph that trains the model with one batch of examples and
    # updates the model parameters.
    train_op = kbody.get_train_op(loss, global_step, scale=scale, clip=False)

    class _LoggerHook(tf.train.SessionRunHook):
      """ Logs loss and runtime."""

      def __init__(self):
        super(_LoggerHook, self).__init__()
        self._step = -1
        self._start_time = 0
        self._log_frequency = FLAGS.log_frequency

      def begin(self):
        self._step = -1

      def before_run(self, run_context):
        self._step += 1
        self._start_time = time.time()
        return tf.train.SessionRunArgs({"loss": loss})

      def should_log(self):
        return self._step % self._log_frequency == 0

      def after_run(self, run_context, run_values):
        duration = time.time() - self._start_time
        loss_value = run_values.results["loss"]
        num_examples_per_step = FLAGS.batch_size
        if self.should_log():
          examples_per_sec = num_examples_per_step / duration
          sec_per_batch = float(duration)
          fstr = ('%s: step %6d, loss = %10.6f (%6.1f examples/sec; %7.3f '
                  'sec/batch)')
          print(fstr % (datetime.now(), self._step, loss_value,
                        examples_per_sec, sec_per_batch))

    saver = tf.train.Saver()
    run_meta = tf.RunMetadata()
    run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)

    class _TimelineHook(tf.train.SessionRunHook):
      """ A hook to output tracing results for further performance analysis. """

      def __init__(self):
        super(_TimelineHook, self).__init__()
        self._counter = -1

      def begin(self):
        self._counter = -1

      def get_ctf(self):
        return join(FLAGS.train_dir, "prof_%d.json" % self._counter)

      def should_save(self):
        return FLAGS.timeline and self._counter % FLAGS.save_frequency == 0

      def after_run(self, run_context, run_values):
        self._counter += 1
        if self.should_save():
          timeline = Timeline(step_stats=run_meta.step_stats)
          ctf = timeline.generate_chrome_trace_format(show_memory=True)
          with open(self.get_ctf(), "w+") as f:
            f.write(ctf)

    with tf.train.MonitoredTrainingSession(
        checkpoint_dir=FLAGS.train_dir,
        save_summaries_steps=FLAGS.save_frequency,
        hooks=[tf.train.StopAtStepHook(last_step=FLAGS.max_steps),
               tf.train.NanTensorHook(loss),
               _LoggerHook(),
               _TimelineHook()],
        config=tf.ConfigProto(
          log_device_placement=FLAGS.log_device_placement)) as mon_sess:

      # Manually restore the previous checkpoint.
      if FLAGS.restart:
        ckpt = tf.train.get_checkpoint_state(FLAGS.train_dir)
        if ckpt and ckpt.model_checkpoint_path:
          saver.restore(mon_sess, ckpt.model_checkpoint_path)
      while not mon_sess.should_stop():
        if FLAGS.timeline:
          mon_sess.run(train_op, options=run_options, run_metadata=run_meta)
        else:
          mon_sess.run(train_op)


if __name__ == "__main__":
  tf.app.run(main=train_model)
