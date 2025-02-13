Deep Deterministic Policy Gradient (DDPG)
=========================================

DDPG is a **model-free**, **deterministic** **off-policy** **actor-critic** algorithm that uses deep function approximators to learn a policy (and to estimate the action-value function) in high-dimensional, **continuous** action spaces

Paper: `Continuous control with deep reinforcement learning <https://arxiv.org/abs/1509.02971>`_

Algorithm implementation
^^^^^^^^^^^^^^^^^^^^^^^^

| Main notation/symbols:
|   - policy function approximator (:math:`\mu_\theta`), critic function approximator (:math:`Q_\phi`)
|   - states (:math:`s`), actions (:math:`a`), rewards (:math:`r`), next states (:math:`s'`), dones (:math:`d`)
|   - loss (:math:`L`)

**Decision making** (:literal:`act(...)`)

| :math:`a \leftarrow \mu_\theta(s)`
| :math:`noise \leftarrow` sample :guilabel:`noise`
| :math:`scale \leftarrow (1 - \text{timestep} \;/` :guilabel:`timesteps` :math:`) \; (` :guilabel:`initial_scale` :math:`-` :guilabel:`final_scale` :math:`) \;+` :guilabel:`final_scale`
| :math:`a \leftarrow \text{clip}(a + noise * scale, {a}_{Low}, {a}_{High})`

**Learning algorithm** (:literal:`_update(...)`)

| :green:`# sample a batch from memory`
| [:math:`s, a, r, s', d`] :math:`\leftarrow` states, actions, rewards, next_states, dones of size :guilabel:`batch_size`
| :green:`# gradient steps`
| **FOR** each gradient step up to :guilabel:`gradient_steps` **DO**
|     :green:`# compute target values`
|     :math:`a' \leftarrow \mu_{\theta_{target}}(s')`
|     :math:`Q_{_{target}} \leftarrow Q_{\phi_{target}}(s', a')`
|     :math:`y \leftarrow r \;+` :guilabel:`discount_factor` :math:`\neg d \; Q_{_{target}}`
|     :green:`# compute critic loss`
|     :math:`Q \leftarrow Q_\phi(s, a)`
|     :math:`L_{Q_\phi} \leftarrow \frac{1}{N} \sum_{i=1}^N (Q - y)^2`
|     :green:`# optimization step (critic)`
|     reset :math:`\text{optimizer}_\phi`
|     :math:`\nabla_{\phi} L_{Q_\phi}`
|     step :math:`\text{optimizer}_\phi`
|     :green:`# compute policy (actor) loss`
|     :math:`a \leftarrow \mu_\theta(s)`
|     :math:`Q \leftarrow Q_\phi(s, a)`
|     :math:`L_{\mu_\theta} \leftarrow - \frac{1}{N} \sum_{i=1}^N Q`
|     :green:`# optimization step (policy)`
|     reset :math:`\text{optimizer}_\theta`
|     :math:`\nabla_{\theta} L_{\mu_\theta}`
|     step :math:`\text{optimizer}_\theta`
|     :green:`# update target networks`
|     :math:`\theta_{target} \leftarrow` :guilabel:`polyak` :math:`\theta + (1 \;-` :guilabel:`polyak` :math:`) \theta_{target}`
|     :math:`\phi_{target} \leftarrow` :guilabel:`polyak` :math:`\phi + (1 \;-` :guilabel:`polyak` :math:`) \phi_{target}`
|     :green:`# update learning rate`
|     **IF** there is a :guilabel:`learning_rate_scheduler` **THEN**
|         step :math:`\text{scheduler}_\theta (\text{optimizer}_\theta)`
|         step :math:`\text{scheduler}_\phi (\text{optimizer}_\phi)`

Configuration and hyperparameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:data:: skrl.agents.torch.ddpg.ddpg.DDPG_DEFAULT_CONFIG

.. literalinclude:: ../../../skrl/agents/torch/ddpg/ddpg.py
   :language: python
   :lines: 15-50
   :linenos:

Spaces and models
^^^^^^^^^^^^^^^^^

The implementation supports the following `Gym spaces <https://www.gymlibrary.dev/content/spaces>`_

.. list-table::
   :header-rows: 1

   * - Gym spaces
     - .. centered:: Observation
     - .. centered:: Action
   * - Discrete
     - .. centered:: :math:`\square`
     - .. centered:: :math:`\square`
   * - Box
     - .. centered:: :math:`\blacksquare`
     - .. centered:: :math:`\blacksquare`
   * - Dict
     - .. centered:: :math:`\blacksquare`
     - .. centered:: :math:`\square`

The implementation uses 4 deterministic function approximators. These function approximators (models) must be collected in a dictionary and passed to the constructor of the class under the argument :literal:`models`

.. list-table::
   :header-rows: 1

   * - Notation
     - Concept
     - Key
     - Input shape
     - Output shape
     - Type
   * - :math:`\mu_\theta(s)`
     - Policy (actor)
     - :literal:`"policy"`
     - observation
     - action
     - :ref:`Deterministic <models_deterministic>`
   * - :math:`\mu_{\theta_{target}}(s)`
     - Target policy
     - :literal:`"target_policy"`
     - observation
     - action
     - :ref:`Deterministic <models_deterministic>`
   * - :math:`Q_\phi(s, a)`
     - Q-network (critic)
     - :literal:`"critic"`
     - observation + action
     - 1
     - :ref:`Deterministic <models_deterministic>`
   * - :math:`Q_{\phi_{target}}(s, a)`
     - Target Q-network
     - :literal:`"target_critic"`
     - observation + action
     - 1
     - :ref:`Deterministic <models_deterministic>`

API
^^^

.. autoclass:: skrl.agents.torch.ddpg.ddpg.DDPG
   :undoc-members:
   :show-inheritance:
   :private-members: _update
   :members:
   
   .. automethod:: __init__
