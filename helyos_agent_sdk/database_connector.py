import uuid
import json
import time

class DatabaseConnector():
    """
    This module defines the DatabaseConnector class.

    The class is responsible for handling remote procedure calls (RPCs) using the AMQP protocol.
    It connects to a Helyos client and makes requests to helyOS database.

    Attributes:
    connection (obj): The pika RabbitMQ connection object .
    helyos_client (obj): The Helyos client object.
    routing_key (str): The routing key for the summary requests.
    username (str): The username for the RabbitMQ.
    channel (obj): The channel object of the connection.
    callback_queue (str): The callback queue for receiving responses.
    response (str): The response received from the RPC call.
    corr_id (str): The unique correlation id for the RPC call.

    Methods:
    init(connection, helyos_client): Initializes the DatabaseConnector object and sets up the necessary attributes.
    on_response(ch, method, props, body): Callback function for handling the response received from the RPC call.
    call(request): Makes a remote procedure call with the given request and returns the response.

    requests can be one of the following: "allAgents", "allYards", "executingMissions", "missionAssignments" or "allMapObjects".

    .. code-block:: python

    helyos_client = HelyOSClient(host='myrabbitmq.com', port=5672, uuid='3452345-52453-43525')
    helyos_client.connect_rabbitmq('my_username', 'secret_password')
    db_rpc = DatabaseConnector(helyos_client)
    agents_summary = db_rpc.call({'query': 'allAgents', 'conditions': {"yard_id": 1}})

    """

    def __init__(self, helyos_client):
        if helyos_client._protocol == 'MQTT':
            raise Exception('Remote procedure call should use AMQP protocoll.')
        self.connection = helyos_client.connection
        self.routing_key = helyos_client.database_routing_key
        self.helyos_client = helyos_client

        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, request):
        """
        :param request: a dictionary containing the query or mutation and condition or data.
                        The query can be one of the following: "allAgents", "allYards", "executingMissions", "missionAssignments","allMapObjects",
                        The mutations can be one of the following: "createMapObjects", "deleteMapObjects", "deleteMapObjectByIds".
                        The condition is a dictionary that specifies additional filtering criteria for the query or deleting.
                        The data is a list of dictionaries containing the data to be inserted.

        :type request: dict
        :return: the requested information based on the provided query and conditions.
        :rtype: an

        Examples:
            >>> db_rpc.call({'query': 'allAgents', 'conditions': {"yard_id": 1}})
            >>> db_rpc.call({'mutation': 'createMapObjects', 'data': [{'name': 'object1', 'type': 'type1', 'yard_id': 1}]})
            >>> db_rpc.call({'mutation': 'deleteMapObjects', 'conditions': {'id': 1}})
            >>> db_rpc.call({'mutation': 'deleteMapObjectByIds', 'conditions': {'ids': [1, 2, 3]}})

        """

        if not self.helyos_client.is_connection_open:
            self.helyos_client.reconnect()
            time.sleep(3)
            self.__init__(self.helyos_client)

        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.helyos_client.publish(routing_key=self.routing_key,
                                   message=json.dumps({'body': request}),
                                   signed=False,
                                   reply_to=self.callback_queue,
                                   corr_id=self.corr_id,
        )

        self.connection.process_data_events(time_limit=None)
        return json.loads(json.loads(self.response)['message'])
