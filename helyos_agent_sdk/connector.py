import logging
import json
from .exceptions import *
from .client import HelyOSClient
from .models import (ASSIGNMENT_STATUS, AGENT_STATE, AGENT_MESSAGE_TYPE, Pose, ASSIGNMENT_MESSAGE_TYPE, INSTANT_ACTIONS_TYPE, WorkProcessResourcesRequest,
                     AssignmentCommandMessage, AssignmentMetadata, AssignmentCancelMessage, AgentCurrentResources, AgentStateBody,
                     AgentStateMessage, AssignmentCurrentStatus)



def parse_assignment_message(self, ch, properties, received_str):
    """ Parse the assignment message and call the callback function.
    :param ch: RabbitMQ channel
    :type ch: Channel
    :param properties: RabbitMQ properties
    :type properties: BasicProperties
    :param received_str: Received message
    :type received_str: string
    
    """
    sender = None
    if hasattr(properties, 'user_id'):
        sender = properties.user_id

    try:
        message_signature = json.loads(received_str).get('signature', None)
        message_str = json.loads(received_str)['message']
        received_message = json.loads(message_str)
        action_type = received_message.get('type', None)

        if action_type == ASSIGNMENT_MESSAGE_TYPE.EXECUTION:
            assignment_metadata = received_message.get('metadata',{}) 
            command_message = {'type': received_message['type'],
                               'uuid': received_message['uuid'],
                               'metadata': AssignmentMetadata(**assignment_metadata),
                               'body': received_message['body'],
                               '_version': received_message['_version']}

            inst_assignm_exec = AssignmentCommandMessage(**command_message)
            return self.assignment_callback(ch, sender, inst_assignm_exec, message_str, message_signature)

        return self.other_assignment_callback(ch,  sender, received_str)
    except Exception as Argument:
        if action_type == ASSIGNMENT_MESSAGE_TYPE.EXECUTION:
            logging.exception('Error occurred while receiving assignment.')    
            return None
        else:
            return self.other_assignment_callback(ch, sender, received_str)



def parse_instant_actions(self, ch, properties, received_str):
    """ Parse the instant action messages and call the callback function.
    :param ch: RabbitMQ channel
    :type ch: Channel
    :param properties: RabbitMQ properties
    :type properties: BasicProperties
    :param received_str: Received message
    :type received_str: string
    """
    sender = None; action_type = None
    if hasattr(properties, 'user_id'):
        sender = properties.user_id

    try:
        message_signature = json.loads(received_str).get('signature', None)
        message_str = json.loads(received_str).get('message', None)
        if message_str is None:
             return self.other_instant_actions_callback(ch, sender, received_str)
        
        received_message = json.loads(message_str)
        action_type = received_message.get('type', None)

        if action_type == INSTANT_ACTIONS_TYPE.CANCEL:
            assignment_metadata = received_message.get('metadata', {}) 
            command_message = {'type': received_message['type'],
                               'uuid': received_message['uuid'],
                               'metadata': AssignmentMetadata(**assignment_metadata),
                               'body': received_message['body'],
                               '_version': received_message['_version']}
            inst_assignm_cancel = AssignmentCancelMessage(**command_message)
            print('call cancel callback')
            return self.cancel_callback(ch, sender, inst_assignm_cancel, message_str, message_signature)

        if action_type == INSTANT_ACTIONS_TYPE.RESERVE:
            inst_wp_clearance = WorkProcessResourcesRequest(
                **received_message['body'])
            return self.reserve_callback(ch, sender, inst_wp_clearance, message_str, message_signature)

        if action_type == INSTANT_ACTIONS_TYPE.RELEASE:
            inst_wp_clearance = WorkProcessResourcesRequest(
                **received_message['body'])
            return self.release_callback(ch, sender, inst_wp_clearance, message_str, message_signature)

        return self.other_instant_actions_callback(ch, sender, received_str )
    
    except Exception as Argument:
        if action_type in [INSTANT_ACTIONS_TYPE.RELEASE, INSTANT_ACTIONS_TYPE.RESERVE,  INSTANT_ACTIONS_TYPE.CANCEL]:
            logging.exception('Error occurred while receiving instan action.')
            return None
        print(action_type, Argument)
        return self.other_instant_actions_callback(ch, sender, received_str)
    

class AgentConnector():
    agent_status = AGENT_STATE.FREE
    agent_pose: Pose = Pose(x=0, y=0, z=0, orientations=[0])
    agent_resources = None
    current_assignment = None

    @property
    def agent_idle_status(self):
        if self.agent_resources:
            if self.agent_resources.reserved:
                return AGENT_STATE.READY

        return AGENT_STATE.FREE

    def __init__(self, helyos_client, pose=None, encrypted=False):
        """ Agent Connector class

            Usage:
            helyos_client = HelyOSClient('rabbitmq.host.com', 5432, uuid='123-456')
            helyos_client.perform_checkin()
            agentConnector = AgentConnector(helyos_client)
            

            The Agent Connector class provides functionality for consuming and publishing messages in the helyOS framework. 
            It ensures proper data formatting compatible with helyOS.

            :param helyos_client: Instance of HelyOS Client. The instance should be "checked in".
            :type helyos_client: HelyOSClient
            :param pose:  (Optional) save the initial agent position in AgentConnector.agent_pose. This may be useful in callback methods.
            :type pose: Pose
            :param encrypted: Set if the published messages should be encrypted, defaults to False.
            :type encrypted: bool

        """
        self.helyos_client = helyos_client
        self.encrypted = encrypted
        if pose:
            self.agent_pose = pose

    __instant_actions_callback = parse_instant_actions
    __assignment_callback = parse_assignment_message

    def assignment_callback(self, ch, sender, received_msg): return print(
        'assignment', sender, received_msg)

    def cancel_callback(self, ch, sender, received_msg): return print(
        'cancel callback', sender, received_msg)

    def reserve_callback(self, ch, sender, received_msg): return print(
        'reserve callback', sender, received_msg)

    def release_callback(self, ch, sender, received_msg): return print(
        'release callback', sender, received_msg)

    def other_instant_actions_callback(self, ch, sender, received_msg): return print(
        'instant_action_callback', sender, received_msg)

    def other_assignment_callback(self, ch, sender, received_msg): return print(
        'other_assignment_callback', sender,  received_msg)

    def consume_instant_action_messages(self, reserve_callback=None, release_callback=None, cancel_callback=None,  other_callback=None):
        """Register the callback functions for instant actions

            :param reserve_callback: reserve_callback(ch:Channel , sender: string, message: WorkProcessResourcesRequest)
            :type reserve_callback: func
            :param release_callback: release_callback(ch, sender, message: WorkProcessResourcesRequest)
            :type release_callback: func
            :param cancel_callback: cancel_callback
            :type cancel_callback: func(ch, sender, message: AssignmentCancelMessage)
            :param other_callback: Non-helyOS related instant action
            :type other_callback: func(ch: Channel, sender:string, message: string)

        """

        if cancel_callback is not None:
            self.cancel_callback = cancel_callback
        if reserve_callback is not None:
            self.reserve_callback = reserve_callback
        if release_callback is not None:
            self.release_callback = release_callback
        if other_callback is not None:
            self.other_instant_actions_callback = other_callback

        def amqp_callback(ch, method, properties, message):
            return parse_instant_actions(self, ch, properties, received_str=message)

        def mqtt_callback(ch, userdata, message):
            return parse_instant_actions(self, ch, {'user_id': None}, received_str=message.payload.decode())

        if self.helyos_client._protocol == 'AMQP':
            self.__instant_actions_callback = amqp_callback

        if self.helyos_client._protocol == 'MQTT':
            self.__instant_actions_callback = mqtt_callback

        self.helyos_client.consume_instant_actions_messages(
            self.__instant_actions_callback)

    def consume_assignment_messages(self, assignment_callback=None, other_callback=None):
        """Register the callback functions for assignments or order (VDA5050)

            :param reserve_callback: assignment_callback(ch, method, properties, received_str)
            :type reserve_callback: func
            :param other_callback: Non-helyOS related instant action
            :type other_callback: func(ch, method, properties, received_str)
        """

        if assignment_callback is not None:
            self.assignment_callback = assignment_callback
        if other_callback is not None:
            self.other_assignment_callback = other_callback

        def amqp_callback(ch, method, properties, message):
            return parse_assignment_message(self, ch, properties, received_str=message)

        def mqtt_callback(ch, userdata, message):
            return parse_assignment_message(self, ch, {'user_id': None}, received_str=message.payload.decode())

        if self.helyos_client._protocol == 'AMQP':
            self.__assignment_callback = amqp_callback

        if self.helyos_client._protocol == 'MQTT':
            self.__assignment_callback = mqtt_callback

        self.helyos_client.consume_assignment_messages(
            self.__assignment_callback)

    def start_listening(self):
        self.helyos_client.start_listening()

    def stop_listening(self):
        self.helyos_client.stop_listening()

    def publish_general_updates(self, body={}, signed=False):
        """
            Updates agent properties of agent: name, code, factsheet, x, y etc.
            This is published in a high-priority queue; the message will not expire until helyOS consume it.
            Therefore, it is recommended to refrain from using this method at high frequencies.
            RabbitMQ clients can access this information by use the routing key = 'agent.{uuid}.update'.

            :param body: Any property of the agent.
            :type body: dict
            :param signed: A boolean indicating whether the published message must be signed (defaults to False)
            :type signed: boolean

        """
        self.helyos_client.publish(
            routing_key=self.helyos_client.update_routing_key,
            message=json.dumps(
                {'type': AGENT_MESSAGE_TYPE.UPDATE.value,
                 'uuid': self.helyos_client.uuid,
                 'body': body,
                 }, sort_keys=True),
            signed=signed
        )

    def publish_state(self, status: AGENT_STATE, resources: AgentCurrentResources = None, assignment_status: AssignmentCurrentStatus = None, signed=False):
        """
            Updates agent and the work processes status. For a good design, this method should be triggered by events.
            This is published in a high-priority queue; the message will not expire until helyOS consume it.
            Therefore, it is recommended to refrain from using this method at high frequencies.
            RabbitMQ clients can access this information by using the routing key = 'agent.{uuid}.state'.

            :param status: Agent status.
            :type status: string | AGENT_STATE
            :param resources: Agent availability information.
            :type resources: AgentCurrentResources
            :param assignment_status: Information about the current (or last) assignment.
            :type assignment_status: AssignmentCurrentStatus
            :param signed: A boolean indicating whether the published message must be signed (defaults to False)
            :type signed: boolean


        """
        self.agent_status = status
        if resources:
            self.agent_resources = resources
        if assignment_status:
            self.current_assignment = assignment_status

        agent_state_body = AgentStateBody(status, resources, assignment_status)
        message = AgentStateMessage(
            uuid=self.helyos_client.uuid, body=agent_state_body)
        message_dict = json.loads(message.to_json())

        self.helyos_client.publish(
            routing_key=self.helyos_client.status_routing_key,
            message=json.dumps(message_dict, sort_keys=True),
            signed=signed
        )

    def publish_sensors(self, x, y, z, orientations, sensors={}, signed=False):
        """ Publishes agent position and sensors. The sensor data format is freely defined by the developer.
            This method should be triggered periodically to ensure a stable helyOS-agent connection. 
            The published information is placed in a low-priority queue and may expire under high load conditions. 
            For high-priority updates, use the method `publish_general_updates()`.    
            RabbitMQ clients can access this information using the routing key 'agent.{uuid}.visualization'.        

            :param x: Agent x position
            :type x: float
            :param y: Agent y position
            :type y: float
            :param orientations: Agent and trailer orientations
            :type orientations: float list
            :param sensors: Agent sensor, user defined (defaults to {}).
            :type sensors: dict
            :param signed: A boolean indicating whether the published message must be signed (defaults to False)
            :type signed: boolean

        """

        self.agent_pose = Pose(x, y, z, orientations)
        self.helyos_client.publish(
            routing_key=self.helyos_client.sensors_routing_key,
            message=json.dumps(
                {'type': AGENT_MESSAGE_TYPE.SENSORS.value,
                 'uuid': self.helyos_client.uuid,
                 'body': {'pose': {'x': x, 'y': y, 'z': z, 'orientations': orientations},
                          'sensors': sensors
                          }
                 }, sort_keys=True),
            signed=signed
        )

    def request_mission(self, mission_name, data, agent_uuids=[],  signed=False):
        """ Request a mission to helyOS. The mission data is freely defined by the application.
            As example, this method could be triggered in the scenario where the agent needs an extra assignments to complete
            a mission, or when it delegates an assignment to other agents.
            RabbitMQ clients can tap this information by using the routing key = 'agent.{uuid}.mission'.

            :param mission_name: requested mission, as defined in helyOS dashboard.
            :type mission_name: name
            :param data: User-defined data
            :type data: dict
            :param agent_uuids: UUID list of agents to be reserved for the mission.
            :type agent_uuids: string list
            :param signed: A boolean indicating whether the published message must be signed (defaults to False)
            :type signed: boolean

        """
        self.helyos_client.publish(
            routing_key=self.helyos_client.mission_routing_key,
            message=json.dumps(
                {'type': AGENT_MESSAGE_TYPE.MISSION.value,
                 'uuid': self.helyos_client.uuid,
                 'body': {'work_process_type_name': mission_name,
                          'data': data,
                          'agent_uuids': agent_uuids,
                          'yard_uid': self.helyos_client.yard_uid,
                          }
                 }, sort_keys=True),
            signed=signed

        )


