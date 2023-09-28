import pika
import uuid
import json
import time
import warnings

class SummaryRPC():
    """
    This module defines the SummaryRPC class.

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
    init(connection, helyos_client): Initializes the SummaryRPC object and sets up the necessary attributes.
    on_response(ch, method, props, body): Callback function for handling the response received from the RPC call.
    call(request): Makes a remote procedure call with the given request and returns the response.

    .. code-block:: python

    helyos_client = HelyOSClient(host='myrabbitmq.com', port=5672, uuid='3452345-52453-43525')
    helyos_client.connect_rabbitmq('my_username', 'secret_password')
    summary_rpc = SummaryRPC(helyos_client)
    agents_summary = summary_rpc.call({'query': 'allAgents', 'conditions': {"yard_id": 1}})

    """

    def __init__(self, helyos_client):
        #  log out the want that this class is deprecated and DatabaseConnector should be used instead
        warnings.warn("SummaryRPC is deprecated and will be removed in future versions. Use DatabaseConnector instead.", DeprecationWarning)
        
        if helyos_client._protocol == 'MQTT':
            raise Exception('Remote procedure call should use AMQP protocoll.')
        self.connection = helyos_client.connection
        self.routing_key = helyos_client.summary_routing_key
        self.username = helyos_client.rbmq_username

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
        :param request: a dictionary containing the query and conditions.
                        The query can be one of the following: "allAgents", "allYards", "executingMissions", "missionAssignments" or "allMapObjects".
                        The conditions specify additional filtering criteria for the query.
        :type request: dict

        :return: the requested information based on the provided query and conditions.
        :rtype: an
        """

        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='xchange_helyos.agents.ul',
            routing_key=self.routing_key,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                user_id=self.username,
                timestamp=int(time.time()*1000),
            ),
            body=json.dumps({'body': request}))
        self.connection.process_data_events(time_limit=None)
        return json.loads(json.loads(self.response)['message'])
