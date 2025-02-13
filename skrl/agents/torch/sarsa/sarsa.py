from typing import Union, Tuple, Dict, Any

import gym
import copy

import torch

from ....memories.torch import Memory
from ....models.torch import Model

from .. import Agent


SARSA_DEFAULT_CONFIG = {
    "discount_factor": 0.99,        # discount factor (gamma)

    "random_timesteps": 0,          # random exploration steps
    "learning_starts": 0,           # learning starts after this many steps

    "learning_rate": 0.5,           # learning rate (alpha)

    "rewards_shaper": None,         # rewards shaping function: Callable(reward, timestep, timesteps) -> reward

    "experiment": {
        "directory": "",            # experiment's parent directory
        "experiment_name": "",      # experiment name
        "write_interval": 250,      # TensorBoard writing interval (timesteps)

        "checkpoint_interval": 1000,        # interval for checkpoints (timesteps)
        "store_separately": False,          # whether to store checkpoints separately
    }
}


class SARSA(Agent):
    def __init__(self, 
                 models: Dict[str, Model], 
                 memory: Union[Memory, Tuple[Memory], None] = None, 
                 observation_space: Union[int, Tuple[int], gym.Space, None] = None, 
                 action_space: Union[int, Tuple[int], gym.Space, None] = None, 
                 device: Union[str, torch.device] = "cuda:0", 
                 cfg: dict = {}) -> None:
        """State Action Reward State Action (SARSA)

        https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.17.2539
        
        :param models: Models used by the agent
        :type models: dictionary of skrl.models.torch.Model
        :param memory: Memory to storage the transitions.
                       If it is a tuple, the first element will be used for training and 
                       for the rest only the environment transitions will be added
        :type memory: skrl.memory.torch.Memory, list of skrl.memory.torch.Memory or None
        :param observation_space: Observation/state space or shape (default: None)
        :type observation_space: int, tuple or list of integers, gym.Space or None, optional
        :param action_space: Action space or shape (default: None)
        :type action_space: int, tuple or list of integers, gym.Space or None, optional
        :param device: Computing device (default: "cuda:0")
        :type device: str or torch.device, optional
        :param cfg: Configuration dictionary
        :type cfg: dict

        :raises KeyError: If the models dictionary is missing a required key
        """
        _cfg = copy.deepcopy(SARSA_DEFAULT_CONFIG)
        _cfg.update(cfg)
        super().__init__(models=models, 
                         memory=memory, 
                         observation_space=observation_space, 
                         action_space=action_space, 
                         device=device, 
                         cfg=_cfg)

        # models
        self.policy = self.models.get("policy", None)

        # checkpoint models
        self.checkpoint_modules["policy"] = self.policy
        
        # configuration
        self._discount_factor = self.cfg["discount_factor"]
        
        self._random_timesteps = self.cfg["random_timesteps"]
        self._learning_starts = self.cfg["learning_starts"]

        self._learning_rate = self.cfg["learning_rate"]

        self._rewards_shaper = self.cfg["rewards_shaper"]

        # create temporary variables needed for storage and computation
        self._current_states = None
        self._current_actions = None
        self._current_rewards = None
        self._current_next_states = None
        self._current_dones = None

    def init(self) -> None:
        """Initialize the agent
        """
        super().init()

    def act(self, states: torch.Tensor, timestep: int, timesteps: int) -> torch.Tensor:
        """Process the environment's states to make a decision (actions) using the main policy

        :param states: Environment's states
        :type states: torch.Tensor
        :param timestep: Current timestep
        :type timestep: int
        :param timesteps: Number of timesteps
        :type timesteps: int

        :return: Actions
        :rtype: torch.Tensor
        """
        # sample random actions
        if timestep < self._random_timesteps:
            return self.policy.random_act(states, taken_actions=None, role="policy")

        # sample actions from policy
        return self.policy.act(states, taken_actions=None, role="policy")

    def record_transition(self, 
                          states: torch.Tensor, 
                          actions: torch.Tensor, 
                          rewards: torch.Tensor, 
                          next_states: torch.Tensor, 
                          dones: torch.Tensor, 
                          infos: Any, 
                          timestep: int, 
                          timesteps: int) -> None:
        """Record an environment transition in memory
        
        :param states: Observations/states of the environment used to make the decision
        :type states: torch.Tensor
        :param actions: Actions taken by the agent
        :type actions: torch.Tensor
        :param rewards: Instant rewards achieved by the current actions
        :type rewards: torch.Tensor
        :param next_states: Next observations/states of the environment
        :type next_states: torch.Tensor
        :param dones: Signals to indicate that episodes have ended
        :type dones: torch.Tensor
        :param infos: Additional information about the environment
        :type infos: Any type supported by the environment
        :param timestep: Current timestep
        :type timestep: int
        :param timesteps: Number of timesteps
        :type timesteps: int
        """
        super().record_transition(states, actions, rewards, next_states, dones, infos, timestep, timesteps)

        # reward shaping
        if self._rewards_shaper is not None:
            rewards = self._rewards_shaper(rewards, timestep, timesteps)

        self._current_states = states
        self._current_actions = actions
        self._current_rewards = rewards
        self._current_next_states = next_states
        self._current_dones = dones

        if self.memory is not None:
            self.memory.add_samples(states=states, actions=actions, rewards=rewards, next_states=next_states, dones=dones)
            for memory in self.secondary_memories:
                memory.add_samples(states=states, actions=actions, rewards=rewards, next_states=next_states, dones=dones)

    def pre_interaction(self, timestep: int, timesteps: int) -> None:
        """Callback called before the interaction with the environment

        :param timestep: Current timestep
        :type timestep: int
        :param timesteps: Number of timesteps
        :type timesteps: int
        """
        pass

    def post_interaction(self, timestep: int, timesteps: int) -> None:
        """Callback called after the interaction with the environment

        :param timestep: Current timestep
        :type timestep: int
        :param timesteps: Number of timesteps
        :type timesteps: int
        """
        if timestep >= self._learning_starts:
            self._update(timestep, timesteps)

        # write tracking data and checkpoints
        super().post_interaction(timestep, timesteps)

    def _update(self, timestep: int, timesteps: int) -> None:
        """Algorithm's main update step

        :param timestep: Current timestep
        :type timestep: int
        :param timesteps: Number of timesteps
        :type timesteps: int
        """
        q_table = self.policy.table()
        env_ids = torch.arange(self._current_rewards.shape[0]).view(-1, 1)
        
        # compute next actions
        next_actions = self.policy.act(self._current_next_states, taken_actions=None, role="policy")[0]

        # update Q-table
        q_table[env_ids, self._current_states, self._current_actions] += self._learning_rate \
            * (self._current_rewards + self._discount_factor * self._current_dones.logical_not() \
                * q_table[env_ids, self._current_next_states, next_actions] \
                    - q_table[env_ids, self._current_states, self._current_actions])
        