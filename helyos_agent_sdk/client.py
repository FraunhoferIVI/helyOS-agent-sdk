import time
from functools import wraps
import pika
import os
import json
import ssl
from .exceptions import *
from helyos_agent_sdk.models import AGENT_STATE
from .crypto import Signing, generate_private_public_keys

AGENTS_UL_EXCHANGE = os.environ.get(
    'AGENTS_UL_EXCHANGE', 'xchange_helyos.agents.ul')
AGENTS_DL_EXCHANGE = os.environ.get(
    'AGENTS_DL_EXCHANGE', 'xchange_helyos.agents.dl')
AGENT_ANONYMOUS_EXCHANGE = os.environ.get(
    'AGENT_ANONYMOUS_EXCHANGE', 'xchange_helyos.agents.anonymous')
REGISTRATION_TOKEN = os.environ.get(
    'REGISTRATION_TOKEN', '0000-0000-0000-0000-0000')


def connect_rabbitmq(rabbitmq_host, rabbitmq_port, username, passwd, enable_ssl=False, ca_certificate=None, temporary=False):
    credentials = pika.PlainCredentials(username, passwd)
    if enable_ssl:
        context = ssl.create_default_context(cadata=ca_certificate)
        if ca_certificate is not None:
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        ssl_options = pika.SSLOptions(context, rabbitmq_host)
    else:
        ssl_options = None

    if temporary:
        params = pika.ConnectionParameters(rabbitmq_host,  rabbitmq_port, '/', credentials, heartbeat=60, blocked_connection_timeout=60,
                                           ssl_options=ssl_options)
    else:
        params = pika.ConnectionParameters(rabbitmq_host,  rabbitmq_port, '/', credentials, heartbeat=3600, blocked_connection_timeout=300,
                                           ssl_options=ssl_options)
    _connection = pika.BlockingConnection(params)
    return _connection



class HelyOSClient():

    def __init__(self, rabbitmq_host, rabbitmq_port=5672, uuid=None, enable_ssl=False, ca_certificate=None,  pubkey=None):
        """ HelyOS client class

            The client implements several functions to facilitate the
            interaction with RabbitMQ. It reads the RabbitMQ exchange names from environment variables
            and it provides the helyOS routing-key names as properties.

            :param rabbitmq_host: RabbitMQ host name (e.g rabbitmq.mydomain.com)
            :type rabbitmq_host: str
            :param rabbitmq_port: RabbitMQ port, defaults to 5672
            :type rabbitmq_port: int
            :param uuid: universal unique identifier fot the agent
            :type uuid: str
            :param enable_ssl: Enable rabbitmq SSL connection, default False.
            :type enable_ssl: boolean, optional
            :param ca_certificate: Certificate authority of the RabbitMQ server, defaults to None
            :type ca_certificate: string (PEM format), optional
            :param pubkey: RSA public key can be saved in helyOS core, defaults to None
            :type pubkey:  string (PEM format), optional

        """
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.ca_certificate = ca_certificate
        self.uuid = uuid
        self.enable_ssl = enable_ssl

        self.connection = None
        self.channel = None
        self.checkin_data = None
        self._protocol = 'AMQP'

        self.tries = 0
        self.rbmq_username = None
        self.rbmq_password = None

        if pubkey is None:
            self.private_key, self.public_key = generate_private_public_keys()
        else:
            self.public_key = pubkey

        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port

    @property
    def checking_routing_key(self):
        """ Routing key value used for check in messages """
        return f'agent.{self.uuid}.checkin'

    @property
    def status_routing_key(self):
        """ Routing key value used to publish agent and assigment states  """

        return f'agent.{self.uuid}.state'

    @property
    def sensors_routing_key(self):
        """ Routing key value used for broadingcasting of positions and sensors  """

        return f'agent.{self.uuid}.visualization'

    @property
    def mission_routing_key(self):
        """ Routing key value used to publish mission requests  """

        return f'agent.{self.uuid}.mission_req'

    @property
    def summary_routing_key(self):
        """ Routing key value used to publish summary requests  """

        return f'agent.{self.uuid}.summary_req'

    @property
    def instant_actions_routing_key(self):
        """ Routing key value used to read instant actions  """

        return f'agent.{self.uuid}.instantActions'

    @property
    def update_routing_key(self):
        """ Routing key value used for agent update messages  """

        return f'agent.{self.uuid}.update'

    @property
    def assignment_routing_key(self):
        """ Routing key value used to read assigment messages  """

        return f'agent.{self.uuid}.assignment'

    def get_checkin_result(self):
        """ get_checkin_result() read the checkin data published by helyOS and save into the HelyOSClient instance
            as `checkin_data`.

         """

        self.tries = 0
        self.guest_channel.start_consuming()

    def auth_required(func):  # pylint: disable=no-self-argument
        @wraps(func)
        def wrap(*args, **kwargs):
            if not args[0].connection:
                raise HelyOSClientAutheticationError(
                    'HelyOSClient is not authenticated. Check the HelyosClient.perform_checkin() method.'
                )
            return func(*args, **kwargs)  # pylint: a disable=not-callable

        return wrap

    def __connect_as_anonymous(self):

        # step 1 - connect anonymously
        try:
            temp_connection = connect_rabbitmq(
                self.rabbitmq_host, self.rabbitmq_port, 'anonymous', 'anonymous', self.enable_ssl, temporary=True)
            self.guest_channel = temp_connection.channel()
        except Exception as inst:
            print(inst)
            raise HelyOSAnonymousConnectionError(
                'Not able to connect as anonymous to rabbitMQ to perform check in.')

        # step 2 - creates a temporary queue to receive checkin response
        temp_queue = self.guest_channel.queue_declare(queue='', exclusive=True)
        self.checkin_response_queue = temp_queue.method.queue
        self.guest_channel.basic_consume(
            queue=self.checkin_response_queue, auto_ack=True, on_message_callback=self.__checkin_callback_wrapper)

    def __prepare_checkin_for_already_connected(self):
        # step 1 - use existent connection
        self.guest_channel = self.channel
        # step 2 - creates a temporary queue to receive checkin response
        temp_queue = self.guest_channel.queue_declare(queue='', exclusive=True)
        self.checkin_response_queue = temp_queue.method.queue
        self.guest_channel.basic_consume(
            queue=self.checkin_response_queue, auto_ack=True, on_message_callback=self.__checkin_callback_wrapper)

    def connect_rabbitmq(self, username, password):
        return self.connect(username, password)

    def connect(self, username, password):
        """
        Creates the connection between agent and the RabbitMQ server.

        .. code-block:: python

            helyos_client = HelyOSClient(host='myrabbitmq.com', port=5672, uuid='3452345-52453-43525')
            helyos_client.connect_rabbitmq('my_username', 'secret_password') #  <===


        :param username:  username previously registered in RabbitMQ server
        :type username: str
        :param password: password previously registered in RabbitMQ server'
        :type password: str
        """

        try:
            self.connection = connect_rabbitmq(self.rabbitmq_host,
                                               self.rabbitmq_port, username, password, self.enable_ssl, self.ca_certificate)
            self.channel = self.connection.channel()
            self.rbmq_username = username

        except Exception as inst:
            raise HelyOSAccountConnectionError(
                f'Not able to connect as {username} to rabbitMQ. {inst}')

    def perform_checkin(self, yard_uid, status=AGENT_STATE.FREE, agent_data={}):
        """
        The check-in procedure registers the agent to a specific yard. helyOS will publish the relevant data about the yard
        and the CA certificate of the RabbitMQ server, which is relevant for SSL connections. Use the method `get_checkin_result()` to retrieve these data.

        The method `connect_rabbitmq()` should run before the check-in, otherwise, it will be assumed that the agent does not have yet a RabbitMQ account.
        In this case, if the environment variable REGISTRATION_TOKEN is set, helyOS will create a RabbitMQ account using the
        uuid as username and returns a password, which can be found in the property `rbmq_password`. This password should be safely stored.

        .. code-block:: python

            helyos_client = HelyOSClient(host='myrabbitmq.com', port=5672, uuid='3452345-52453-43525')
            helyos_client.connect_rabbitmq('my_username', 'secret_password')
            helyos_client.perform_checkin(yard_uid='yard_A', status='free')  #  <===
            helyOS_client.get_checkin_result()                               #  <===


        :param yard_uid: Yard UID
        :type yard_uid: str
        :param status: Agent status, defaults to 'free'
        :type status: str
        """
        if self.connection:
            self.__prepare_checkin_for_already_connected()
            username = self.rbmq_username
        else:
            self.__connect_as_anonymous()
            username = 'anonymous'

        self.yard_uid = yard_uid
        checkin_msg = {'type': 'checkin',
                       'uuid': self.uuid,
                       'body': {'yard_uid': yard_uid,
                                'status': status,
                                'public_key': self.public_key.decode('utf-8'),
                                'public_key_format': 'PEM',
                                'registration_token': REGISTRATION_TOKEN,
                                **agent_data},
                       }

        self.guest_channel.basic_publish(exchange=AGENT_ANONYMOUS_EXCHANGE,
                                         routing_key=self.checking_routing_key,
                                         properties=pika.BasicProperties(
                                             reply_to=self.checkin_response_queue, user_id=username, timestamp=int(time.time()*1000)),
                                         body=json.dumps(checkin_msg, sort_keys=True))

    def __checkin_callback_wrapper(self, channel, method, properties, received_str):
        try:
            self.__checkin_callback(received_str)
            channel.stop_consuming()
        except Exception as inst:
            self.tries += 1
            print(f'try {self.tries}')
            if self.tries > 3:
                channel.stop_consuming()

    def __checkin_callback(self, received_str):
        received_message_str = json.loads(received_str)['message']
        received_message = json.loads(received_message_str)

        msg_type = received_message['type']
        if msg_type != 'checkin':
            print('waiting response...')
            return

        body = received_message['body']
        response_code = body.get('response_code', 500)
        if response_code != '200':
            print(body)
            message = body.get('message', 'Check in refused')
            raise HelyOSCheckinError(f'{message}: code {response_code}')

        password = body.pop('rbmq_password', None)
        self.ca_certificate = body.get('ca_certificate', self.ca_certificate)

        if password:
            self.connection = connect_rabbitmq(
                self.rabbitmq_host, self.rabbitmq_port, body['rbmq_username'], password, self.enable_ssl, self.ca_certificate)
            self.channel = self.connection.channel()
            self.rbmq_username = body['rbmq_username']
            self.rbmq_password = password

            print('uuid', self.uuid)
            print('username', body['rbmq_username'])
            print('password', len(password)*'*')

        self.uuid = received_message['uuid']
        self.checkin_data = body

    @auth_required
    def publish(self, routing_key, message, encrypted=False, exchange=AGENTS_UL_EXCHANGE):
        """ Publish message in RabbitMQ

            :param routing_key: RabbitMQ routing_key
            :type routing_key: str
            :param encrypted: If this message should be encrypted, defaults to False
            :type encrypted: str
            :param exchange: RabbitMQ exchange, defaults to env.AGENTS_UL_EXCHANGE
            :type exchange: str
        """

        try:
            self.channel.basic_publish(exchange, routing_key,
                                       properties=pika.BasicProperties(
                                           user_id=self.rbmq_username, timestamp=int(time.time()*1000)),
                                       body=message)
        except ConnectionResetError:
            self.channel = self.connection.channel()
            self.channel.basic_publish(exchange, routing_key,
                                       properties=pika.BasicProperties(
                                           user_id=self.rbmq_username, timestamp=int(time.time()*1000)),
                                       body=message)

    @auth_required
    def set_assignment_queue(self, exchange=AGENTS_DL_EXCHANGE):
        self.assignment_queue = self.channel.queue_declare(queue='')
        self.channel.queue_bind(queue=self.assignment_queue.method.queue,
                                exchange=exchange, routing_key=self.assignment_routing_key)
        return self.assignment_queue

    @auth_required
    def set_instant_actions_queue(self, exchange=AGENTS_DL_EXCHANGE):
        self.instant_actions_queue = self.channel.queue_declare(queue='')
        self.channel.queue_bind(queue=self.instant_actions_queue.method.queue,
                                exchange=exchange, routing_key=self.instant_actions_routing_key)
        return self.instant_actions_queue

    @auth_required
    def consume_assignment_messages(self, assignment_callback):
        self.set_assignment_queue()
        self.channel.basic_consume(queue=self.assignment_queue.method.queue, auto_ack=True,
                                   on_message_callback=assignment_callback)

    @auth_required
    def consume_instant_actions_messages(self, instant_actions_callback):
        """ Receive instant actions messages.
            Instant actions are used by helyOS to reserve, release or cancel an assignment.

            :param instant_actions_callback: call back for instant actions
            :type instant_actions_callback: func

        """

        self.set_instant_actions_queue()
        self.channel.basic_consume(queue=self.instant_actions_queue.method.queue, auto_ack=True,
                                   on_message_callback=instant_actions_callback)

    def start_listening(self):
        self.channel.start_consuming()

    def stop_listening(self):
        self.channel.stop_consuming()
