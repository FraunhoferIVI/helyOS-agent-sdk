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

* RabbitMQ client for communication with helyOS core.
* Support for both AMQP and MQTT protocols.
* Definition of agent and assignment status.
* Easy access to helyOS assignments and instant actions through callbacks.
* SSL support and application-level security with RSA signature. 
* Automatic reconnection to handle connection disruptions.

### Install

```
pip install helyos_agent_sdk

```
### Usage

```python

from helyos_agent_sdk import HelyOSClient, AgentConnector

# Connect via AMQP
helyOS_client = HelyOSClient(rabbitmq_host, rabbitmq_port, uuid=AGENT_UID)

# Or connect via MQTT
# helyOS_client = HelyOSMQTTClient(rabbitmq_host, rabbitmq_port, uuid=AGENT_UID)

helyOS_client.connnect(username, password)

# Check in yard
initial_agent_data = {'name': "vehicle name", 'pose': {'x':-30167, 'y':-5415, 'orientations':[0, 0]}, 'geometry':{"my_custom_format": {}}}
helyOS_client.perform_checkin(yard_uid='1', agent_data=initial_agent_data, status="free")
helyOS_client.get_checkin_result() # yard data

# Communication
agent_connector = AgentConnector(helyOS_client)
agent_connector.publish_sensors(x=-30167, y=3000, z=0, orientations=[1500, 0], sensor= {"my_custom_format": {}})

# ... #

agent_connector.publish_state(status, resources, assignment_status)

# ... #

agent_connector.consume_instant_action_messages(my_reserve_callback, my_release_callback, my_cancel_assignm_callback, any_other_callback)
agent_connector.consume_assignment_messages(my_assignment_callback)
agent_connector.start_listening()


```


### Contributing

Keep it simple. Keep it minimal.

### Authors

*   Carlos E. Viol Barbosa
*   ...

### License

This project is licensed under the MIT License
