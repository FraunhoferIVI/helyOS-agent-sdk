from datetime import datetime as dt
from functools import wraps
import pika
from .exceptions import *

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import os, json

AGENTS_UL_EXCHANGE = os.environ.get('AGENTS_UL_EXCHANGE', "xchange_helyos.agents.ul")
AGENTS_DL_EXCHANGE = os.environ.get('AGENTS_DL_EXCHANGE', "xchange_helyos.agents.dl")
AGENT_ANONYMOUS_EXCHANGE = os.environ.get('AGENT_ANONYMOUS_EXCHANGE', "xchange_helyos.agents.anonymous")
REGISTRATION_TOKEN = os.environ.get('REGISTRATION_TOKEN','0000-0000-0000-0000-0000')


def connect_rabbitmq(rabbitmq_host, rabbitmq_port, username, passwd, temporary=False):
    credentials = pika.PlainCredentials(username, passwd)
    if temporary:
        params = pika.ConnectionParameters(rabbitmq_host,  rabbitmq_port, '/', credentials,heartbeat=60, blocked_connection_timeout=60)
    else:
        params = pika.ConnectionParameters(rabbitmq_host,  rabbitmq_port, '/', credentials,heartbeat=3600,blocked_connection_timeout=300)
    _connection = pika.BlockingConnection(params)
    return _connection    


def generate_private_public_keys():
    key = RSA.generate(2048)
    priv = key.export_key(format='PEM')
    pub = key.publickey().export_key(format='PEM')
    return priv, pub
    


class HelyOSClient():
    connection = None
    checkin_data = None
    tries = 0
    
    def __init__(self, rabbitmq_host, rabbitmq_port=5672, uuid=None, pubkey=None):
        """ HelyOS client class

            The client implements several functions to make it easier to
            interact with rabbitMQ. It reads the rabbitMQ exchange names from environment variables
            and it encloses the routing-key names as properties.

            :param rabbitmq_host: RabbitMQ host name (e.g rabbitmq.mydomain.com)
            :type rabbitmq_host: str
            :param rabbitmq_port: RabbitMQ port, defaults to 5672
            :type rabbitmq_port: int
            :param uuid: universal unique identifier fot the agent
            :type uuid: str
            :param pubkey: RSA public key to be saved in helyOS core, defaults to None
            :type pubkey: str, optional

        """
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.uuid = uuid
        
        if pubkey is None:
            self.private_key, self.public_key = generate_private_public_keys()
        else:
            self.public_key = pubkey

        self.rabbitmq_host = rabbitmq_host    
        self.rabbitmq_port = rabbitmq_port    


    @property    
    def checking_routing_key(self):
        """ Routing key value used for check in messages """
        return f"agent.{self.uuid}.checkin"

    @property    
    def status_routing_key(self):
        """ Routing key value used to publish agent and assigment states  """

        return f"agent.{self.uuid}.state"

    @property    
    def sensors_routing_key(self):
        """ Routing key value used for broadingcasting of positions and sensors  """

        return f"agent.{self.uuid}.visualization"

    @property    
    def mission_routing_key(self):
        """ Routing key value used to publish mission requests  """

        return f"agent.{self.uuid}.mission"

    @property    
    def instant_actions_routing_key(self):
        """ Routing key value used to read instant actions  """

        return f"agent.{self.uuid}.instantActions"
    
    @property    
    def update_routing_key(self):
        """ Routing key value used for agent update messages  """

        return f"agent.{self.uuid}.update"
    
    @property    
    def assignment_routing_key(self):
        """ Routing key value used to read assigment messages  """

        return f"agent.{self.uuid}.assignment"
          
    def get_checkin_result(self):
        """ get_checkin_result() read the checkin data published by helyOS and save into the HelyOSClient instance
            as `checkin_data`.

         """

        self.tries = 0
        self.guest_channel.start_consuming()

  
    def auth_required(func):  # pylint: disable=no-self-argument
        @wraps(func)
        def wrap(*args, **kwargs):
            if not args[0].connection :
                raise HelyOSClientAutheticationError(
                    "HelyOSClient is not authenticated. Check the HelyosClient.perform_checkin() method."
                )
            return func(*args, **kwargs)  # pylint: a disable=not-callable

        return wrap

    def __connect_as_anonymous(self):

        # step 1 - connect anonymously
        try:
            temp_connection = connect_rabbitmq(self.rabbitmq_host, self.rabbitmq_port,'anonymous', 'anonymous', temporary=True)        
            self.guest_channel = temp_connection.channel()
        except Exception as inst:
            print(inst)
            raise HelyOSAnonymousConnectionError(
                    "Not able to connect as anonymous to rabbitMQ to perform check in.")
    
        
        # step 2 - creates a temporary queue to receive checkin response
        temp_queue = self.guest_channel.queue_declare(queue='', exclusive=True)            
        self.checkin_response_queue = temp_queue.method.queue 
        self.guest_channel.basic_consume(queue=self.checkin_response_queue, auto_ack=True, on_message_callback=self.__checkin_callback)

    def perform_checkin(self, yard_uid, status='free', agent_data={}):
        """ Check in the agent

        :param yard_uid: Yard UID
        :type yard_uid: str
        :param status: Agent status, defaults to 'free'
        :type status: str
        """
        self.__connect_as_anonymous()
        self.yard_uid = yard_uid
        checkin_msg = {  'type': 'checkin',
                         'uuid': self.uuid,
                         'status': status,
                         'body': {'yard_uid': yard_uid, 
                                  'public_key':self.public_key.decode("utf-8"),  
                                  'public_key_format': 'PEM', 
                                  'registration_token': REGISTRATION_TOKEN,
                                  **agent_data},
                       }

        self.guest_channel.basic_publish(exchange = AGENT_ANONYMOUS_EXCHANGE,
                                  routing_key =  self.checking_routing_key,
                                  properties=pika.BasicProperties(reply_to = self.checkin_response_queue),
                                  body=json.dumps(checkin_msg))
        

    def __checkin_callback(self, ch, method, properties, received_str):
        received_message_str = json.loads(received_str)['message']    
        received_message = json.loads(received_message_str)
        
        msg_type = received_message['type']
        if msg_type != 'checkin':
            print("waiting response...")
            return
        
        body = received_message['body']
        response_code = body.get('response_code', 500)
        if response_code!='200':
            print(body)
            raise HelyOSCheckinError(f"Check in refused: code {response_code}")
            
        password = body['rbmq_password']
        try:
            self.connection = connect_rabbitmq(self.rabbitmq_host, self.rabbitmq_port, body['rbmq_username'], password)
            self.channel = self.connection.channel()
            self.uuid = received_message['uuid']
            self.checkin_data = body
            ch.stop_consuming()
            
            print('uuid', self.uuid)
            print('username', body['rbmq_username'])
            print('password', body['rbmq_password'])
        except  Exception as inst: 
            self.tries += 1
            print(f"try {self.tries}")
            if self.tries > 3:
                ch.stop_consuming()


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
            self.channel.basic_publish(exchange, routing_key, body=message)
        except ConnectionResetError:
            self.channel = self.connection.channel()
            self.channel.basic_publish(exchange, routing_key, body=message)

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

