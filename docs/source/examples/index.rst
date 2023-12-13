Examples
========

The following examples provides clear explanations for connecting to helyOS,
publishing messages, and receiving messages using the Agent Connector.
It also emphasizes security considerations.


Connect to helyOS via AMQP
--------------------------
To establish a connection to HelyOS using AMQP, follow these steps:

.. code-block:: python

    from helyos_agent_sdk import HelyOSClient

    helyos_client = HelyOSClient("dev2.rabbitmq.net", uuid="01234-01234-01234")
    helyos_client.connect(username="01234-01234-01234", password="secret_password")
    helyos_client.perform_checkin(yard_uid="0", agent_data={'name':"my truck", 'factsheet':user_defined_dict})
    helyos_client.get_checkin_result()
    print(helyos_client.checkin_data) # Data from helyOS containing yard information.


Connect to helyOS via MQTT
--------------------------
To establish a connection to HelyOS using MQTT, use the `HelyOSMQTTClient` as shown below:

.. code-block:: python

    from helyos_agent_sdk import HelyOSMQTTClient

    helyos_client = HelyOSMQTTClient("dev2.rabbitmq.net", uuid="01234-01234-01234")
    helyos_client.connect(username="01234-01234-01234", password="secret_password")
    helyos_client.perform_checkin(yard_uid="0", agent_data={'name':"my truck", 'factsheet':user_defined_dict})
    helyos_client.get_checkin_result()
    print(helyos_client.checkin_data) # Data containing yard information.


Connect to helyOS via AMQP without an account
---------------------------------------------
If the agent does not have an account yet but possesses the helyOS registration token,
you can call `perform_checkin()` method without running the `connect()` method.
helyOS will automatically create a Rabbitmq account using the UUID as the username.

.. code-block:: python

    from helyos_agent_sdk import HelyOSClient

    if os.environ.get('REGISTRATION_TOKEN', None):
        helyos_client = HelyOSClient("dev2.rabbitmq.net", uuid="01234-01234-01234")
        # not used => helyos_client.connect(username="01234-01234-01234", password="secret_password")
        helyos_client.perform_checkin(yard_uid="0", agent_data={'name':"my truck", 'factsheet':user_defined_dict})
        helyos_client.get_checkin_result()
        print(helyos_client.checkin_data) # Data containing yard and new authentication credentials.



Connect to helyOS with SSL
--------------------------
.. code-block:: python

    from helyos_agent_sdk import HelyOSMQTTClient, HelyOSClient
    
    if PROTOCOL == "AMQP":   
        Client = HelyOSClient
        port = 5671
    if PROTOCOL == "MQTT":
        Client = HelyOSMQTTClient
        port = 8883

    with open(CACERTIFICATE_FILENAME, "r") as f:
        CA_CERTIFICATE = f.read()
        helyos_client = Client("dev2.rabbitmq.net", port, uuid="01234-01234-01234",
                                enable_ssl=True, ca_certificate=CA_CERTIFICATE)

    helyos_client.connect(username="01234-01234-01234", password="secret_password")
    helyos_client.perform_checkin(yard_uid="0", agent_data={'name':"my truck", 'factsheet':user_defined_dict})
    helyos_client.get_checkin_result()
    print(helyos_client.checkin_data) 


Create an Agent Connector and publish messages to helyOS
----------------------------------------------------------
To create an Agent Connector and publish messages to HelyOS, follow these steps:

.. code-block:: python

    from helyos_agent_sdk import AgentConnector
    from helyos_agent_sdk.models import AssignmentCurrentStatus

    agent_connector = AgentConnector(helyos_client)
    assignment_status = AssignmentCurrentStatus(id=1, status='executing', result={})
    agent_connector.publish_state(status='free', assignment_status= assignment_status)
    agent_connector.publish_sensors(x=43243, y=423423, z=0, orientations=[0], sensors={'temperature': 36})
    agent_connector.publish_general_updates({'x': 43243, 'name': "my truck"})


Signing Published Messages for Increased Security
----------------------------------------------------------
To enhance security, you can sign the published messages using the agent's private key.
If private and public keys are not provided, the `HelyOSClient` will generate a new key pair at initialization.
The agent's public is loaded to helyOS core in the checkin process and can be upadated using the admin dashboard.

.. code-block:: python

    from helyos_agent_sdk import AgentConnector, HelyOSClient
    from helyos_agent_sdk.models import AssignmentCurrentStatus

    helyos_client = HelyOSClient("dev2.rabbitmq.net", uuid="01234-01234-01234",
                                  agent_pubkey=AGENT_PUBLIC_KEY, agent_privkey=AGENT_PRIVATE_KEY)
    helyos_client.connect(username="01234-01234-01234", password="secret_password")
    helyos_client.perform_checkin(yard_uid="0", agent_data={'name':"my truck", 'factsheet':user_defined_dict})
    helyos_client.get_checkin_result()
    
    agent_connector = AgentConnector(helyos_client)
    assignment_status = AssignmentCurrentStatus(id=1, status='executing', result={})
    agent_connector.publish_state(status='free', assignment_status= assignment_status, signed=True)
    agent_connector.publish_sensors(x=43243, y=423423, sensors={'temperature': 36}, signed=False)
    agent_connector.publish_general_updates({x=43243, name='your truck', geometry=user_defined_dict, signed=True)




Use the agent connector to receive messsages from helyOS
---------------------------------------------------------
.. code-block:: python

    from helyos_agent_sdk.crypto import verify_signature

    def example_callback(ch, sender, parsed_data, message_str, signature):
        if PROTOCOL == "AMQP" and sender is not 'helyos_core':
            throw Exception("Invalid sender")
        if PROTOCOL == "MQTT":
            verify_signature(message_str, signature, helyos_client.helyos_public_key)
        print("callback", parsed_data)
        

    agent_connector.consume_assignment_messages(assignment_callback=example_callback) # assignment
    agent_connector.consume_instant_action_messages( reserve_callback=example_callback,# reserve for mission
                                                 release_callback=example_callback,# release from mission
                                                 cancel_callback=example_callback) # cancel assignment
    agent_connector.start_listening()
  
    


In the `example_callback()`, the parameter sender is the validated username of the RabbitMQ account of the client that sent the message. 
This parameter is not available when use MQTT; sender=`None` in this case. For MQTT, you may use the signature parameter to validate the message sender.

In the `publish_sensors()`, the parameter sensors has an arbitrary data format. 
If you don't have any strict requirement, you may use the 
helyos-native data format:

  | \[field_id: string\]: 
  |              "value" : string | number, required
  |              "title" : string, required
  |              "type" :  string = "string" or "number", required
  |              "description": string,
  |              "unit":      string,
  |              "minimum" :  number,
  |              "maximum" :  number,
  |              "maxLength": number,
  |              "minLength": number


Example:

.. code-block:: python

       sensors = {
         "sensor_set_2": {
           "velocity_01": {
                  "title": "velocity",
                  "value": 20,
                  "type": "number",
                  "unit": "km/h",
                  "minimum": 0,
                  "maximum": 200
             },
             "back_door_status": {
                  "title": "Truck door",
                  "value": "half-open",
                  "type": "string",
                  "unit": "km/h",
                  "minLength": 5,
                  "maxLength": 10
             }
        }




You may check :mod:`helyos_agent_sdk.client.HelyOSClient` for more details regarding the current methods.

For resource attributes you may refer to :mod:`helyos_agent_sdk.models`
