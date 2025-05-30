# Copyright 2025 The kauldron Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import shlex
import sys

from absl import flags
from kauldron import kd
from examples import mnist_autoencoder
from kauldron.xm._src import kauldron_utils
from kauldron.xm._src import sweep_cfg_utils

with kd.konfig.imports():
  from flax import linen as nn  # pylint: disable=g-import-not-at-top


def sweep():
  for bs in [16, 32]:
    yield {
        'eval_ds.batch_size': bs,
        'train_ds.batch_size': bs,
        'aux.model_size': 'big' if bs == 16 else 'small',
    }


def sweep_model():
  for m in [
      nn.Dense(12),
      nn.Sequential([]),
  ]:
    yield {'model': m}


def test_sweep():
  from kauldron.utils import sweep_utils_test as config_module  # pylint: disable=g-import-not-at-top

  all_sweep_info = list(
      sweep_cfg_utils._sweeps_from_module(
          module=config_module, names=['model', '']
      )
  )
  assert len(all_sweep_info) == 4  # Cross product

  sweep0 = kauldron_utils._encode_sweep_item(all_sweep_info[0])
  assert sweep0.job_kwargs == {
      'cfg.eval_ds.batch_size': '16',
      'cfg.train_ds.batch_size': '16',
      'cfg.aux.model_size': 'big',
      'cfg.model': '{"__qualname__": "flax.linen:Dense", "0": 12}',
  }
  sweep0 = kauldron_utils.deserialize_job_kwargs(sweep0.job_kwargs)
  assert sweep0 == {
      'eval_ds.batch_size': 16,
      'train_ds.batch_size': 16,
      'aux.model_size': 'big',
      'model': {'__qualname__': 'flax.linen:Dense', '0': 12},
  }


def test_sweep_overwrite():
  argv = shlex.split(
      # fmt: off
      'my_app'
      f' --cfg={mnist_autoencoder.__file__}'
      ' --cfg.seed=12'
      ' --cfg.train_ds.name=imagenet'
      ' --cfg.train_ds.transforms[0].keep[0]=other_image'
      ' --cfg.model="{\\"__qualname__\\": \\"flax.linen:Dense\\", \\"0\\": 12}"'
      # fmt: on
  )

  flag_values = flags.FlagValues()
  with _replace_sys_argv(argv):
    sweep_flag = kd.konfig.DEFINE_config_file(
        'cfg',
        mnist_autoencoder.__file__,
        'Config file to use for the sweep.',
        flag_values=flag_values,
    )
    flag_values(argv)

  cfg = sweep_flag.value
  assert cfg.seed == 12
  assert cfg.train_ds.transforms[0].keep == ['other_image']
  assert cfg.train_ds.name == 'imagenet'
  assert cfg.model == nn.Dense(12)
  assert isinstance(cfg.model, kd.konfig.ConfigDict)


@contextlib.contextmanager
def _replace_sys_argv(argv):
  old_argv = sys.argv
  sys.argv = argv
  try:
    yield
  finally:
    sys.argv = old_argv
