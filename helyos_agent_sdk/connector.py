from datetime import datetime as dt
import json
from .exceptions import *
from .client import HelyOSClient
from .models import (ASSIGNMENT_STATUS, AGENT_STATE, Pose, ASSIGNMENT_MESSAGE_TYPE, INSTANT_ACTIONS_TYPE, WorkProcessResourcesRequest,
                    AssignmentCommandMessage, AssignmentMetadata, AssignmentCancelMessage, AgentCurrentResources, AgentStateBody, 
                    AgentStateMessage, AssignmentCurrentStatus)

            

def parse_assignment_message(self, ch, method, properties, received_str):    
    received_message_str = json.loads(received_str)['message']    
    received_message = json.loads(received_message_str)
    action_type = received_message.get('type', None)
    
    if action_type == ASSIGNMENT_MESSAGE_TYPE.EXECUTION:
        command_message = { 'type' : received_message['type'],
                            'work_process_id': received_message['work_process_id'],
                            'assignment_metadata': AssignmentMetadata(**received_message['assignment_metadata']),
                            'body': received_message['body'],
                            '_version': received_message['_version'] }
                                                                          
        inst_assignm_exec = AssignmentCommandMessage(**command_message)
        return self.assignment_callback(ch, method, properties, inst_assignm_exec)
        
    return self.other_assignment_callback(ch, method, properties, received_str)
    
    
def parse_instant_actions(self, ch, method, properties, received_str):
    received_message_str = json.loads(received_str)['message']    
    received_message = json.loads(received_message_str)
    action_type = received_message.get('type', None)

    if action_type == INSTANT_ACTIONS_TYPE.CANCEL:
        command_message = { 'type' : received_message['type'],
                            'work_process_id': received_message['work_process_id'],
                            'assignment_metadata': AssignmentMetadata(**received_message['assignment_metadata']),
                            'body': received_message['body'],
                            '_version': received_message['_version'] }
        inst_assignm_cancel = AssignmentCancelMessage(**command_message)      
        print("call cancel callback")
        return self.cancel_callback(ch, method, properties, inst_assignm_cancel)

    if action_type == INSTANT_ACTIONS_TYPE.RESERVE:
        inst_wp_clearance = WorkProcessResourcesRequest(**received_message['body'])
        return self.reserve_callback(ch, method, properties, inst_wp_clearance)

    if action_type == INSTANT_ACTIONS_TYPE.RELEASE:
        inst_wp_clearance = WorkProcessResourcesRequest(**received_message['body'])
        return self.release_callback(ch, method, properties, inst_wp_clearance)   
        
    if action_type == INSTANT_ACTIONS_TYPE.WPCLEREANCE:  # Backward compatibility
        work_process_id = received_message['body']['wp_id']        
        operation_types_required = received_message['body']['operation_types_required']
        reserved = received_message['body']['reserved']
        inst_wp_clearance = WorkProcessResourcesRequest(work_process_id, operation_types_required, reserved)
        return self.reserve_callback(ch, method, properties, inst_wp_clearance)

    return self.other_instant_actions_callback(ch, method, properties, received_str)
    


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

            The agent connector allows the developer to consume and publish messages correctly in helyOS framework.
            It implements the data formating compatible with helyOS.
             
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
    assignment_callback = lambda  self, ch, method, properties, received_msg : print("assignment", received_msg)
    cancel_callback = lambda self, ch, method, properties, received_msg : print("cancel callback", received_msg)
    reserve_callback = lambda self, ch, method, properties, received_msg : print("reserve callback", received_msg)
    release_callback = lambda self, ch, method, properties, received_msg : print("release callback", received_msg)
    other_instant_actions_callback = lambda self, ch, method, properties, received_msg : print("instant_action_callback", received_msg)
    other_assignment_callback = lambda self, ch, method, properties, received_msg : print("other_assignment_callback", received_msg)
        

    def consume_instant_action_messages(self, reserve_callback=None, release_callback=None, cancel_callback=None,  other_callback=None):
        """Register the callback functions for instant actions
        
            :param reserve_callback: reserve_callback(ch, method, properties, received_str) 
            :type reserve_callback: func
            :param release_callback: release_callback(ch, method, properties, received_str) 
            :type release_callback: func 
            :param cancel_callback: cancel_callback 
            :type cancel_callback: func(ch, method, properties, received_str)
            :param other_callback: Non-helyOS related instant action
            :type other_callback: func(ch, method, properties, received_str) 

        """


        if cancel_callback is not None: self.cancel_callback = cancel_callback
        if reserve_callback is not None: self.reserve_callback = reserve_callback
        if release_callback is not None: self.release_callback = release_callback
        if other_callback is not None: self.other_instant_actions_callback = other_callback

        self.helyos_client.consume_instant_actions_messages(self.__instant_actions_callback)
        

    def consume_assignment_messages(self, assignment_callback=None, other_callback=None):
        """Register the callback functions for assignments or order (VDA5050)
        
            :param reserve_callback: assignment_callback(ch, method, properties, received_str) 
            :type reserve_callback: func
            :param other_callback: Non-helyOS related instant action
            :type other_callback: func(ch, method, properties, received_str) 
        """
        
        if assignment_callback is not None: self.assignment_callback = assignment_callback 
        if other_callback is not None: self.other_assignment_callback = other_callback

        self.helyos_client.consume_assignment_messages(self.__assignment_callback)

    def start_consuming(self):
        self.helyos_client.channel.start_consuming()
        
        
    def stop_consuming(self):
        self.helyos_client.channel.stop_consuming()


    def publish_general_updates(self, body={}):
        """ 
            Updates agent properties of agent: name, code, factsheet, etc.
            This is published in a low-priority queue to helyOS; in very high load conditions, some messages
            may be expired before helyOS consumption.
            Any other client can tap this information by use the routing key = 'agent.{uuid}.update'.

        """
        self.helyos_client.publish( 
                                      routing_key = self.helyos_client.update_routing_key,
                                      message=json.dumps(
                                              {'type': 'agent_update',
                                              'uuid': self.helyos_client.uuid, 
                                              'body': body,
                                               })
                                     )  

    def publish_state(self, status: AGENT_STATE, resources: AgentCurrentResources=None, assignment_status: AssignmentCurrentStatus=None):
        """ 
            Updates agent and the work processes status. For a good design, this method should be triggered by events.
            The data is published in a priviledged queue to helyOS and the message is always available for helyOS consumption.
            Other rabbitmq clients can tap this information by using the routing key = 'agent.{uuid}.state'.

            :param status: Agent status.
            :type status: string | AGENT_STATE
            :param resources: Agent availability information.
            :type resources: AgentCurrentResources    
            :param assignment_status: Information about the current (or last) assignment.
            :type assignment_status: AssignmentCurrentStatus


        """
        self.agent_status = status
        if resources: self.agent_resources = resources
        if assignment_status: self.current_assignment = assignment_status
        

        agent_state_body = AgentStateBody(status, resources, assignment_status)
        message = AgentStateMessage(uuid=self.helyos_client.uuid, body= agent_state_body)
        
        self.helyos_client.publish( 
                                      routing_key = self.helyos_client.status_routing_key,
                                      message= message.to_json()
                                     )  
        
        
    def publish_sensors(self, x, y, z, orientations, sensors={}):
        """ Publishes agent position and sensors. The sensor data format is freely defined by the application.
            This method should be triggered periodically to ensure the helyOS-agent connection.
            This is published in a low-priority queue to helyOS; in very high load conditions, some of the messages
            may be expired before the helyOS consumption. Any rabbitmq client can tap this information by using the 
            routing key = 'agent.{uuid}.visualization'.

            :param x: Agent x position
            :type x: float
            :param y: Agent y position
            :type y: float
            :param orientations: Agent and trailer orientations
            :type orientations: float list
            :param sensors: Agent sensor, user defined. defaults to {}
            :type sensors: dict   

        """
        
        self.agent_pose = Pose(x,y,z,orientations)
        self.helyos_client.publish(
                                      routing_key = self.helyos_client.sensors_routing_key,
                                      message= json.dumps(
                                               {   'type': 'agent_sensors',
                                                   'uuid': self.helyos_client.uuid, 
                                                   'body': { 'pose': {'x':x,'y':y, 'z':z, 'orientations': orientations},
                                                             'sensors': sensors
                                                           }
                                                })
                                     )        
        
    def request_mission(self, mission_name, data, tools_uuids = [], sched_start_at=None):
        """ Request a mission to helyOS. The mission data is freely defined by the application.
            As example, this method could be triggered in the scenario where the agent needs an extra assignments to complete
            a mission, or when it delegates to other agents. Other rabbitmq clients can tap this information by using the 
            routing key = 'agent.{uuid}.mission'.

            :param mission_name: requested mission, as defined in helyOS dashboard.
            :type mission_name: name
            :param data: User-defined data
            :type data: dict
            :param tools_uuids: UUID list of agents to be reserved for the mission.
            :type tools_uuids: string list
            :param sched_start_at: Mission starting, user defined. defaults to None
            :type sched_start_at: DateTime   

        """
        self.helyos_client.publish(
                                      routing_key = self.helyos_client.mission_routing_key,
                                      message=  json.dumps(
                                                  {'type': 'mission_request',
                                                   'uuid': self.helyos_client.uuid, 
                                                   'body': { 'work_process_type_name': mission_name,
                                                             'data': data,
                                                             'tools_uuids': tools_uuids,
                                                             'yard_uid': self.helyos_client.yard_uid,
                                                             'sched_start_at': sched_start_at
                                                           }
                                                })
                                     )        
        
        
  
        

def agent_checkin_to_helyos(uuid, yard_uid, agent_data, status="free", pubkey=None):
    '''
    agent_checkin_helyos(uuid, yard_uid, agent_data, status="free", pubkey=None)   
    Helper to perform the check in of the agent {uuid} to helyOS at the yard {yard_uid}.
    It excutes the following operations:
    
    * step 1 - instantiate client object (this will connect anonously to rabbitmq to exchange checkin data.
               The anononymous connection last 60 seconds.
    * step 2 - send the check-in data 
    * step 3 - subscribe to the temporary queue to get checkin results

    '''
     
    # step 1 - create connection object
    client_obj = HelyOSClient(uuid, pubkey)    
    # step 2 - send the check-in data
    client_obj.perform_checkin(yard_uid, status, agent_data)
    # step 3 - load checkin result
    client_obj.get_checkin_result()
    
    return client_obj 




