import os
import sys
import time
from datetime import datetime
import gym
import gym_gazebo2
import tensorflow as tf
import multiprocessing

import threading

from importlib import import_module
from baselines import bench, logger
from baselines.ppo2 import ppo2
from baselines.common.vec_env.dummy_vec_env import DummyVecEnv

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
        # first try to imptrain_ppo2_mlp.pyort the alg module from baselines
        alg_module = import_module('.'.join(['baselines', alg, submodule]))
    except ImportError:
        # then from rl_algs
        alg_module = import_module('.'.join(['rl_' + 'algs', alg, submodule]))

    return alg_module

def get_learn_function(alg, submodule=None):
    return get_alg_module(alg, submodule).learn

def get_learn_function_defaults(alg, env_type):
    try:
        alg_defaults = get_alg_module(alg, 'defaults')
        kwargs = getattr(alg_defaults, env_type)()
    except (ImportError, AttributeError):
        kwargs = {}
    return kwargs

leg_name = ""

def make_env_limb():
    env = gym.make('PhantomXLeg-v0')
    env.set_info(main_env.info)
    # env.set_episode_size(alg_kwargs['nsteps'])
    env.leg_name = leg_name
    os.makedirs(logger.get_dir() + "/" + leg_name, exist_ok=True)
    env = bench.Monitor(env, logger.get_dir() + "/" + leg_name + "/log" and os.path.join(logger.get_dir() + "/" + leg_name + "/log"),
                        allow_early_resets=True)
    return env


# Get dictionary from baselines/ppo2/defaults
env_type = 'phantomx_mlp'
alg_kwargs = get_learn_function_defaults('ppo2', env_type)
# Create needed folders
timedate = datetime.now().strftime('%Y-%m-%d_%Hh%Mmin')
logdir = '/tmp/ros2learn/' + alg_kwargs['env_name'] + '/dppo2_mlp/' + timedate

# Generate tensorboard file
format_strs = os.getenv('MARA_LOG_FORMAT', 'stdout,log,csv,tensorboard').split(',')
logger.configure(os.path.abspath(logdir), format_strs)
with open(logger.get_dir() + "/parameters.txt", 'w') as out:
    out.write(
        'num_layers = ' + str(alg_kwargs['num_layers']) + '\n'
        + 'num_hidden = ' + str(alg_kwargs['num_hidden']) + '\n'
        + 'layer_norm = ' + str(alg_kwargs['layer_norm']) + '\n'
        + 'nsteps = ' + str(alg_kwargs['nsteps']) + '\n'
        + 'nminibatches = ' + str(alg_kwargs['nminibatches']) + '\n'
        + 'lam = ' + str(alg_kwargs['lam']) + '\n'
        + 'gamma = ' + str(alg_kwargs['gamma']) + '\n'
        + 'noptepochs = ' + str(alg_kwargs['noptepochs']) + '\n'
        + 'log_interval = ' + str(alg_kwargs['log_interval']) + '\n'
        + 'ent_coef = ' + str(alg_kwargs['ent_coef']) + '\n'
        + 'cliprange = ' + str(alg_kwargs['cliprange']) + '\n'
        + 'vf_coef = ' + str(alg_kwargs['vf_coef']) + '\n'
        + 'max_grad_norm = ' + str(alg_kwargs['max_grad_norm']) + '\n'
        + 'seed = ' + str(alg_kwargs['seed']) + '\n'
        + 'value_network = ' + alg_kwargs['value_network'] + '\n'
        + 'network = ' + alg_kwargs['network'] + '\n'
        + 'total_timesteps = ' + str(alg_kwargs['total_timesteps']) + '\n'
        + 'save_interval = ' + str(alg_kwargs['save_interval']) + '\n'
        + 'env_name = ' + alg_kwargs['env_name'] + '\n'
        + 'transfer_path = ' + str(alg_kwargs['transfer_path']) )


main_env = gym.make('PhantomX-v0')
# main_env.set_episode_size(alg_kwargs['nsteps'])

# main_env = bench.Monitor(main_env, logger.get_dir() and os.path.join(logger.get_dir()), allow_early_resets=True)
# left_env = DummyVecEnv([make_env_left])
# right_env = DummyVecEnv([make_env_right])

leg_envs = {}
learners = {}
legs = ['lf', 'lm', 'lr', 'rf',  'rm', 'rr']

for leg in legs:
        leg_name = leg
        leg_envs[leg] = DummyVecEnv([make_env_limb])
        learners[leg] = get_learn_function('ppo2')

transfer_path = alg_kwargs['transfer_path']
# Remove unused parameters for training
alg_kwargs.pop('env_name')
alg_kwargs.pop('trained_path')
alg_kwargs.pop('transfer_path')

if transfer_path is not None:
    # Do transfer learning
    # learn(env=left_env, load_path=transfer_path, **alg_kwargs)
    pass
else:
    threads = []
    print("starting threads")
    for idx, leg in enumerate(legs):
        alg_kwargs['seed'] = idx
        threads.append(threading.Thread(target=learners[leg], kwargs=dict(env=leg_envs[leg], **alg_kwargs)))
    for thread in threads:
        thread.start()

    # l_thread = threading.Thread(target=learn, kwargs=dict(env=left_env, **alg_kwargs))
    # r_thread = threading.Thread(target=learn, kwargs=dict(env=right_env, **alg_kwargs))
    # l_thread.start()
    # r_thread.start()
    print("threads started")
    while True:
        main_env.info.execute_action()
        main_env.info.execute_reset()
        time.sleep(1/1000)
