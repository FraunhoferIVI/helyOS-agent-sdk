from functools import wraps
import os
import json
import ssl
from .exceptions import *
import paho.mqtt.client as mqtt
import time
from .crypto import Signing, generate_private_public_keys

AGENTS_UL_EXCHANGE = os.environ.get(
    'AGENTS_UL_EXCHANGE', 'xchange_helyos.agents.ul')
AGENTS_DL_EXCHANGE = os.environ.get(
    'AGENTS_DL_EXCHANGE', 'xchange_helyos.agents.dl')
AGENT_ANONYMOUS_EXCHANGE = os.environ.get(
    'AGENT_ANONYMOUS_EXCHANGE', 'xchange_helyos.agents.anonymous')
REGISTRATION_TOKEN = os.environ.get(
    'REGISTRATION_TOKEN', '0000-0000-0000-0000-0000')
AGENTS_MQTT_EXCHANGE = os.environ.get(
    'AGENTS_MQTT_EXCHANGE', 'xchange_helyos.agents.mqtt')


def connect_mqtt(rabbitmq_host, rabbitmq_port, username, passwd, enable_ssl=False, ca_certificate=None, temporary=False):
    global mqtt_msg
    LOGMSG = ['success, connection accepted',
              'connection refused, bad protocol',
              'refused, client-id error',
              'refused, service unavailable',
              'refused, bad username or password',
              'refused, not authorized'
              ]
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(username, passwd)
    mqtt_msg = 'not connected'

    def on_connect(client, userdata, flags, rc):
        global mqtt_msg
        mqtt_msg = LOGMSG[rc]

    mqtt_client.on_connect = on_connect

    if enable_ssl:
        context = ssl.create_default_context(cadata=ca_certificate)
        if ca_certificate is not None:
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        mqtt_client.tls_set_context(context=context)

    if temporary:
        mqtt_client._connect_timeout = 60
    else:
        mqtt_client._connect_timeout = 300

    mqtt_client.connect(rabbitmq_host, rabbitmq_port)
    started = time.time()
    while time.time() - started < 3.0:
        mqtt_client.loop()
        if mqtt_client.is_connected():
            return mqtt_client

    raise Exception(mqtt_msg)


class HelyOSMQTTClient():

    def __init__(self, rabbitmq_host, rabbitmq_port=1883, uuid=None, enable_ssl=False, ca_certificate=None, 
                 helyos_public_key=None, agent_privkey=None, agent_pubkey=None ):
        """ HelyOS MQTT client class

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
            :type enable_ssl: bool, optional
            :param ca_certificate: Certificate authority of the RabbitMQ server, defaults to None
            :type ca_certificate: string (PEM format), optional
            :param helyos_public_key: helyOS RSA public key to verify the helyOS message signature.
            :type helyos_public_key:  string (PEM format), optional
            :param agent_privkey: Agent RSA private key, defaults to None
            :type agent_privkey:  string (PEM format), optional
            :param agent_pubkey: Agent RSA public key is saved in helyOS core, defaults to None
            :type agent_pubkey:  string (PEM format), optional


        """
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.ca_certificate = ca_certificate
        self.helyos_public_key = helyos_public_key
        self.uuid = uuid
        self.enable_ssl = enable_ssl

        self.connection = None
        self.channel = None
        self.checkin_data = None
        self._protocol = 'MQTT'

        self.tries = 0
        self.rbmq_username = None
        self.rbmq_password = None

        if agent_pubkey is None or agent_privkey is None:
            self.private_key, self.public_key = generate_private_public_keys()
        else:
            self.private_key, self.public_key = agent_privkey, agent_pubkey

        self.signing_helper = Signing(self.private_key)

        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port

    @property
    def checking_routing_key(self):
        """ MQTT Topic value used for check in messages """
        return f'agent/{self.uuid}/checkin'

    @property
    def status_routing_key(self):
        """ MQTT Topic value used to publish agent and assigment states  """

        return f'agent/{self.uuid}/state'

    @property
    def sensors_routing_key(self):
        """ MQTT Topic value used for broadingcasting of positions and sensors  """

        return f'agent/{self.uuid}/visualization'

    @property
    def mission_routing_key(self):
        """ MQTT Topic value used to publish mission requests  """

        return f'agent/{self.uuid}/mission_req'

    @property
    def summary_routing_key(self):
        """ MQTT Topic value used to publish summary requests  """

        return f'agent/{self.uuid}/summary_req'

    @property
    def instant_actions_routing_key(self):
        """ MQTT Topic value used to read instant actions  """

        return f'agent/{self.uuid}/instantActions'

    @property
    def update_routing_key(self):
        """ MQTT Topic value used for agent update messages  """

        return f'agent/{self.uuid}/update'

    @property
    def assignment_routing_key(self):
        """ MQTT Topic value used to read assigment messages  """

        return f'agent/{self.uuid}/assignment'

    def get_checkin_result(self):
        """ get_checkin_result() read the checkin data published by helyOS and save into the HelyOSClient instance
            as `checkin_data`.
         """
        self.tries = 0
        self.guest_channel.loop_start()

    def auth_required(func):  # pylint: disable=no-self-argument
        @wraps(func)
        def wrap(*args, **kwargs):
            if not args[0].connection:
                raise HelyOSClientAutheticationError(
                    'HelyOSClient is not authenticated. Check the HelyosClient.connect() method.'
                )
            return func(*args, **kwargs)  # pylint: a disable=not-callable

        return wrap

    def __connect_as_anonymous(self):
        raise HelyOSAnonymousConnectionError(
            'Anonymous check-in is implemented only for AMPQ agents. You must manually create an account.')

    def __prepare_checkin_for_already_connected(self):
        # step 1 - use existent connection
        self.guest_channel = self.channel
        # step 2 - creates a temporary topic to receive checkin response
        temp_topic = f'agent/{self.uuid}/checkinresponse'
        self.checkin_response_queue = temp_topic
        self.guest_channel.subscribe(temp_topic)
        self.guest_channel.message_callback_add(
            temp_topic, self.__checkin_callback_wrapper)

    def connect(self, username, password):
        """
        Creates the connection between agent and the message broker server.

        .. code-block:: python

            helyos_client = HelyOSClient(host='myrabbitmq.com', port=5672, uuid='3452345-52453-43525')
            helyos_client.connect_rabbitmq('my_username', 'secret_password') #  <===


        :param username:  username previously registered in RabbitMQ server
        :type username: str
        :param password: password previously registered in RabbitMQ server'
        :type password: str
        """

        try:
            self.connection = connect_mqtt(self.rabbitmq_host, self.rabbitmq_port,
                                           username, password, self.enable_ssl, self.ca_certificate)
            self.channel = self.connection
            self.rbmq_username = username

        except Exception as inst:
            print(inst)
            raise HelyOSAccountConnectionError(
                f'Not able to connect as {username}.')

    def perform_checkin(self, yard_uid, status='free', agent_data={}, signed=False):
        """
        The check-in procedure registers the agent to a specific yard. helyOS will publish the relevant data about the yard
        and the CA certificate of the RabbitMQ server, which is relevant for SSL connections. Use the method `get_checkin_result()` to retrieve these data.

        The method `connect()` should run before the `perform_checkin()`, otherwise, it will be assumed that the agent does not have yet a RabbitMQ account.
        In this case, if the environment variable REGISTRATION_TOKEN is set, helyOS will create a RabbitMQ account using the
        uuid as username and returns a password, which can be found in the property `rbmq_password`. This password should be safely stored.

        .. code-block:: python

            helyos_client = HelyOSClient(host='myrabbitmq.com', port=1883, uuid='3452345-52453-43525')
            helyos_client.connect('my_username', 'secret_password')
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
                       'status': status,
                       'replyTo': self.checkin_response_queue,
                       'body': {'yard_uid': yard_uid,
                                'public_key': self.public_key.decode('utf-8'),
                                'public_key_format': 'PEM',
                                'registration_token': REGISTRATION_TOKEN,
                                **agent_data},
                       'header': {'timestamp': int(time.time()*1000)}
                       }
        
        message = json.dumps(checkin_msg, sort_keys=True)
        signature = None
        if signed:
            signature = list(self.signing_helper.return_signature(message))

        body = json.dumps({'message': message, 'signature': signature}, sort_keys=True)

        self.guest_channel.publish(
            self.checking_routing_key, payload=body)

    def __checkin_callback_wrapper(self, client, userdata, message):
        try:
            self.__checkin_callback(str(message.payload.decode()))
            # self.channel.loop_stop()   COMMENT: After the loop stop, I am not able to publish
        except Exception as inst:
            print('error check-in callback', inst)
            client.loop_stop()

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
        if self.helyos_public_key is None:
            self.helyos_public_key = body.get('helyos_public_key', self.helyos_public_key)

        if password:
            self.connection = connect_mqtt(self.rabbitmq_host, self.rabbitmq_port,
                                           body['rbmq_username'], password, self.enable_ssl, self.ca_certificate)
            self.channel = self.connection.channel()
            self.rbmq_username = body['rbmq_username']
            self.rbmq_password = password

            print('uuid', self.uuid)
            print('username', body['rbmq_username'])
            print('password', len(password)*'*')

        self.uuid = received_message['uuid']
        self.checkin_data = body

    @auth_required
    def publish(self, routing_key, message, signed=False, exchange=AGENTS_MQTT_EXCHANGE):
        """ Publish message in RabbitMQ
            :param message: Message to be transmitted
            :type message: str
            :param routing_key: MQTT topic name
            :type routing_key: str
            :param encrypted: If this message should be encrypted, defaults to False
            :type encrypted: str
            :param exchange: RabbitMQ exchange, cannot be changed, fixed to env.AGENTS_MQTT_EXCHANGE
            :type exchange: str
        """
        signature = None
        if signed:
            signature = self.signing_helper.return_signature(message).hex()
        
        body = json.dumps({'message': message, 'signature': signature}, sort_keys=True)

        self.channel.publish(routing_key, payload=body)

    @auth_required
    def set_assignment_queue(self, exchange=AGENTS_DL_EXCHANGE):
        """ There is no queues in MQTT protocol """
        return None

    @auth_required
    def set_instant_actions_queue(self, exchange=AGENTS_DL_EXCHANGE):
        """ There is no queues in MQTT protocol """
        return None

    @auth_required
    def consume_assignment_messages(self, assignment_callback):
        """ Subscribe to the MQTT assignment topic """
        mqtt_topic = self.assignment_routing_key
        self.channel.subscribe(mqtt_topic)
        self.channel.message_callback_add(mqtt_topic, assignment_callback)

    @auth_required
    def consume_instant_actions_messages(self, instant_actions_callback):
        """ Receive instant actions messages.
            Instant actions are used by helyOS to reserve, release or cancel an assignment.

            :param instant_actions_callback: call back for instant actions
            :type instant_actions_callback: func

        """

        mqtt_topic = self.instant_actions_routing_key
        self.channel.subscribe(mqtt_topic)
        self.channel.message_callback_add(mqtt_topic, instant_actions_callback)

    def start_listening(self):
        self.channel.loop_start()

    def stop_listening(self):
        self.channel.loop_stop()
