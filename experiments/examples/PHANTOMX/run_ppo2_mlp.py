import os
import sys
import time
import gym
import gym_gazebo2
import numpy as np
import multiprocessing
import tensorflow as tf

from importlib import import_module
from baselines import bench, logger
from baselines.ppo2 import model as ppo2
from baselines.common import set_global_seeds
from baselines.common.vec_env.dummy_vec_env import DummyVecEnv
from baselines.common.vec_env.vec_normalize import VecNormalize
from baselines.common.policies import build_policy

ncpu = multiprocessing.cpu_count()

if sys.platform == 'darwin':
    ncpu //= 2

config = tf.ConfigProto(allow_soft_placement=True,
                        intra_op_parallelism_threads=ncpu,
                        inter_op_parallelism_threads=ncpu,
                        log_device_placement=False)

config.gpu_options.allow_growth = True

tf.Session(config=config).__enter__()

def get_alg_module(alg, submodule=None):
    submodule = submodule or alg
    try:
        # first try to import the alg module from baselines
        alg_module = import_module('.'.join(['baselines', alg, submodule]))
    except ImportError:
        # then from rl_algs
        alg_module = import_module('.'.join(['rl_' + 'algs', alg, submodule]))

    return alg_module

def get_learn_function_defaults(alg, env_type):
    try:
        alg_defaults = get_alg_module(alg, 'defaults')
        kwargs = getattr(alg_defaults, env_type)()
    except (ImportError, AttributeError):
        kwargs = {}
    return kwargs

def constfn(val):
    def f(_):
        return val
    return f

def make_env():
    env = gym.make(defaults['env_name'])
    env.set_episode_size(defaults['nsteps'])
    env = bench.Monitor(env, logger.get_dir() and os.path.join(logger.get_dir()), allow_early_resets=True)

    return env

# Get dictionary from baselines/ppo2/defaults
defaults = get_learn_function_defaults('ppo2', 'phantomx_mlp')

env = DummyVecEnv([make_env])

set_global_seeds(defaults['seed'])

alg_kwargs ={ 'num_layers': defaults['num_layers'], 'num_hidden': defaults['num_hidden'] }
policy = build_policy(env, defaults['network'], **alg_kwargs)

nenvs = env.num_envs
ob_space = env.observation_space
ac_space = env.action_space
nbatch = nenvs * defaults['nsteps']
nbatch_train = nbatch // defaults['nminibatches']

make_model = lambda : ppo2.Model(policy=policy, ob_space=ob_space, ac_space=ac_space, nbatch_act=nenvs,
                                nbatch_train=nbatch_train,
                                nsteps=defaults['nsteps'], ent_coef=defaults['ent_coef'], vf_coef=defaults['vf_coef'],
                                max_grad_norm=defaults['max_grad_norm'])

model = make_model()

model.load('/tmp/training_data/dockerv1.3/PhantomX-v0/ppo2_mlp/2019-12-03_17h02min/main/checkpoints/07550')

obs = env.reset()
loop = True
while loop:
    actions = model.step(obs)[0]
    obs, reward, done, _  = env.step(actions)
