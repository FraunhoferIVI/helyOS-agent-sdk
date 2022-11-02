<div id="top"></div>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/">
    <img src="helyos_logo.png" alt="Logo"  height="80">
    <img src="truck.png" alt="Logo"  height="80">
  </a>

  <h3 align="center">helyOS Agent SDK</h3>

  <p align="center">
    Methods and data strrctures to connect autonomous vehicles to helyOS.
    <br />
    <a href="https://fraunhoferivi.github.io/helyOS-agent-sdk/"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/">View Demo</a>
    ·
    <a href="https://github.com/FraunhoferIVI/helyOS-agent-sdk/issues">Report Bug</a>
    ·
    <a href="https://github.com/FraunhoferIVI/helyOS-agent-sdk/issues">Request Feature</a>
  </p>
</div>

## About The Project

The helyos-agent-sdk python package encloses methods and data structures definitions that facilitate the connection to helyOS core through rabbitMQ.

### List of features

*   RabbitMQ client to communicate with helyOS. 
*   Check-in method.
*   Agent and assignment status definitions. 
*   Easy access to helyOS assignments via callbacks. 
*   Application-level encryption.

### Install

```
pip install helyos_agent_sdk

```
### Usage

```python
os.environ['AGENTS_UL_EXCHANGE'] = "xchange_helyos.agents.ul"
os.environ['AGENTS_DL_EXCHANGE'] = "xchange_helyos.agents.dl"
os.environ['AGENT_ANONYMOUS_EXCHANGE'] = "xchange_helyos.agents.anonymous"
from helyos_agent_sdk import HelyOSClient, AgentConnector

# Check in
helyOS_client = HelyOSClient(rabbitmq_host, rabbitmq_port, uuid=AGENT_UID)
helyOS_client.perform_checkin(yard_uid='1', agent_data=agent_data, status="free")
helyOS_client.get_checkin_result()


# Communication
agent_connector = AgentConnector(helyOS_client)
agent_connector.publish_sensors(x=-30167, y=3000, z=0, orientations=[1500, 0], sensor= {"my_sensor": 12})

# ... #

agentConnector.publish_state(status, resources, assignment_status)

# ... #

agentConnector.consume_instant_action_messages(my_reserve_callback, my_release_callback, my_cancel_assignm_callback, any_other_callback)
agentConnector.consume_assignment_messages(my_assignment_callback)
agentConnector.start_consuming()


```


### Contributing

Keep it simple. Keep it minimal.

### Authors 

*   Carlos E. Viol Barbosa
*   ...

### License

This project is licensed under the MIT License