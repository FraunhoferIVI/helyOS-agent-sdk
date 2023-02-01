Examples
========


Create a HelyOS Client
--------------------------
.. code-block:: python

    >>> from agent_helyos_sdk import HelyOSClient
    >>>
    >>> helyos_client = HelyOSClient("dev2.rabbitmq.net", uuid="01234-01234-01234")
    >>> helyos_client.perform_checkin(agent_data={'name':"my truck", 'factsheet':factsheet_dict})
    >>> print(helyos_client.checkin_data) # Data returned from helyOS containing yard information.

Create an Agent Connector and publish messages to helyOS
----------------------------------------------------------
.. code-block:: python

    >>> from agent_helyos_sdk import AgentConnector
    >>> agent_connector = AgentConnector(helyos_client)
    >>> agent_connector.publish_state(state="free", wp_process=wp_process)
    >>> agent_connector.publish_sensors(x=43243, y=423423, sensors={'temperature': 36})

The parameter sensors has an arbrittary data format. 
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


Use the agent connector to receive messsages from helyOS
---------------------------------------------------------
.. code-block:: python

    >>> example_callback = lambda ch, method, properties, received_str : print("callback", received_str)
    >>> agent_connector.consume_assignments(assignment_callback=example_callback) # assignment
    >>> agent_connector.consume_instant_actions( reserve_callback=example_callback,# reserve for mission
                                                 release_callback=example_callback,# release from mission
                                                 cancel_callback=example_callback) # cancel assignment
    




You may check :mod:`helyos_agent_sdk.client.HelyOSClient` for more details regarding the current methods.

For resource attributes you may refer to :mod:`helyos_agent_sdk.models`
