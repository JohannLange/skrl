from typing import Union, List

import tqdm

import torch

from ...envs.torch import Wrapper
from ...agents.torch import Agent


def generate_equally_spaced_scopes(num_envs: int, num_agents: int) -> List[int]:
    """Generate a list of equally spaced scopes for the agents

    :param num_envs: Number of environments
    :type num_envs: int
    :param num_agents: Number of agents
    :type num_agents: int

    :raises ValueError: If the number of agents is greater than the number of environments

    :return: List of equally spaced scopes
    :rtype: List[int]
    """
    scopes = [int(num_envs / num_agents)] * num_agents
    if sum(scopes):
        scopes[-1] += num_envs - sum(scopes)
    else:
        raise ValueError("The number of agents ({}) is greater than the number of environments ({})" \
            .format(num_agents, num_envs))
    return scopes


class Trainer():
    def __init__(self,
                 env: Wrapper,
                 agents: Union[Agent, List[Agent]],
                 agents_scope : List[int] = [],
                 cfg: dict = {}) -> None:
        """Base class for trainers

        :param env: Environment to train on
        :type env: skrl.env.torch.Wrapper
        :param agents: Agents to train
        :type agents: Union[Agent, List[Agent]]
        :param agents_scope: Number of environments for each agent to train on (default: [])
        :type agents_scope: tuple or list of integers
        :param cfg: Configuration dictionary (default: {})
        :type cfg: dict, optional
        """
        self.cfg = cfg
        self.env = env
        self.agents = agents
        self.agents_scope = agents_scope

        # get configuration
        self.timesteps = self.cfg.get('timesteps', 0)
        self.headless = self.cfg.get("headless", False)

        self.initial_timestep = 0

        # setup agents
        self.num_agents = 0
        self._setup_agents()

    def __str__(self) -> str:
        """Generate a string representation of the trainer

        :return: Representation of the trainer as string
        :rtype: str
        """
        string = "Trainer: {}".format(repr(self))
        string += "\n  |-- Number of parallelizable environments: {}".format(self.env.num_envs)
        string += "\n  |-- Number of agents: {}".format(self.num_agents)
        string += "\n  |-- Agents and scopes:"
        if self.num_agents > 1:
            for agent, scope in zip(self.agents, self.agents_scope):
                string += "\n  |     |-- agent: {}".format(type(agent))
                string += "\n  |     |     |-- scope: {} environments ({}:{})".format(scope[1] - scope[0], scope[0], scope[1])
        else:
            string += "\n  |     |-- agent: {}".format(type(self.agents))
            string += "\n  |     |     |-- scope: {} environment(s)".format(self.env.num_envs)
        return string

    def _setup_agents(self) -> None:
        """Setup agents for training

        :raises ValueError: Invalid setup
        """
        # validate agents and their scopes
        if type(self.agents) in [tuple, list]:
            # single agent
            if len(self.agents) == 1:
                self.num_agents = 1
                self.agents = self.agents[0]
                self.agents_scope = [1]
            # parallel agents
            elif len(self.agents) > 1:
                self.num_agents = len(self.agents)
                # check scopes
                if not len(self.agents_scope):
                    print("[WARNING] The agents' scopes are empty, they will be generated as equal as possible")
                    self.agents_scope = [int(self.env.num_envs / len(self.agents))] * len(self.agents)
                    if sum(self.agents_scope):
                        self.agents_scope[-1] += self.env.num_envs - sum(self.agents_scope)
                    else:
                        raise ValueError("The number of agents ({}) is greater than the number of parallelizable environments ({})" \
                            .format(len(self.agents), self.env.num_envs))
                elif len(self.agents_scope) != len(self.agents):
                    raise ValueError("The number of agents ({}) doesn't match the number of scopes ({})" \
                        .format(len(self.agents), len(self.agents_scope)))
                elif sum(self.agents_scope) != self.env.num_envs:
                    raise ValueError("The scopes ({}) don't cover the number of parallelizable environments ({})" \
                        .format(sum(self.agents_scope), self.env.num_envs))
                # generate agents' scopes
                index = 0
                for i in range(len(self.agents_scope)):
                    index += self.agents_scope[i]
                    self.agents_scope[i] = (index - self.agents_scope[i], index)
            else:
                raise ValueError("A list of agents is expected")
        else:
            self.num_agents = 1

    def train(self) -> None:
        """Train the agents

        :raises NotImplementedError: Not implemented
        """
        raise NotImplementedError

    def eval(self) -> None:
        """Evaluate the agents

        :raises NotImplementedError: Not implemented
        """
        raise NotImplementedError

    def start(self) -> None:
        """Start training

        This method is deprecated in favour of the '.train()' method
        """
        # TODO: remove this method in future versions
        print("[WARNING] Trainer.start() method is deprecated in favour of the '.train()' method")

    def single_agent_train(self) -> None:
        """Train a single agent

        This method executes the following steps in loop:

        - Pre-interaction
        - Compute actions
        - Interact with the environments
        - Render scene
        - Record transitions
        - Post-interaction
        - Reset environments
        """
        assert self.num_agents == 1, "This method is only valid for a single agent"

        # reset env
        states = self.env.reset()

        for timestep in tqdm.tqdm(range(self.initial_timestep, self.timesteps)):

            # pre-interaction
            self.agents.pre_interaction(timestep=timestep, timesteps=self.timesteps)

            # compute actions
            with torch.no_grad():
                actions, _, _ = self.agents.act(states, timestep=timestep, timesteps=self.timesteps)

            # step the environments
            next_states, rewards, dones, infos = self.env.step(actions)

            # render scene
            if not self.headless:
                self.env.render()

            # record the environments' transitions
            with torch.no_grad():
                self.agents.record_transition(states=states,
                                              actions=actions,
                                              rewards=rewards,
                                              next_states=next_states,
                                              dones=dones,
                                              infos=infos,
                                              timestep=timestep,
                                              timesteps=self.timesteps)

            # post-interaction
            self.agents.post_interaction(timestep=timestep, timesteps=self.timesteps)

            # reset environments
            with torch.no_grad():
                if dones.any():
                    states = self.env.reset()
                else:
                    states.copy_(next_states)

        # close the environment
        self.env.close()

    def single_agent_eval(self) -> None:
        """Evaluate the agents sequentially

        This method executes the following steps in loop:

        - Compute actions (sequentially)
        - Interact with the environments
        - Render scene
        - Reset environments
        """
        assert self.num_agents == 1, "This method is only valid for a single agent"

        # reset env
        states = self.env.reset()

        for timestep in tqdm.tqdm(range(self.initial_timestep, self.timesteps)):

            # compute actions
            with torch.no_grad():
                actions, _, _ = self.agents.act(states, timestep=timestep, timesteps=self.timesteps)

            # step the environments
            next_states, rewards, dones, infos = self.env.step(actions)

            # render scene
            if not self.headless:
                self.env.render()

            with torch.no_grad():
                # write data to TensorBoard
                super(type(self.agents), self.agents).record_transition(states=states,
                                                                        actions=actions,
                                                                        rewards=rewards,
                                                                        next_states=next_states,
                                                                        dones=dones,
                                                                        infos=infos,
                                                                        timestep=timestep,
                                                                        timesteps=self.timesteps)
                super(type(self.agents), self.agents).post_interaction(timestep=timestep, timesteps=self.timesteps)

                # reset environments
                if dones.any():
                    states = self.env.reset()
                else:
                    states.copy_(next_states)

        # close the environment
        self.env.close()
