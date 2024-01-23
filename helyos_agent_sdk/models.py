from copy import deepcopy
from dataclasses_json import dataclass_json
from dataclasses import dataclass, field
from typing import List, Optional
from typing_extensions import Literal
from enum import Enum
from datetime import datetime


# ---- CONSTANTS ------ #

VERSION = '3.0.0'


class ASSIGNMENT_STATUS(str, Enum):
    ACTIVE = 'active'
    SUCCEEDED = 'succeeded'
    CANCELED = 'canceled'
    ABORTED = 'aborted'
    FAILED = 'failed'
    TO_EXECUTE = 'to_execute'
    EXECUTING = 'executing'


class AGENT_STATE(str, Enum):
    NOT_AUTO = 'not_automatable'
    FREE = 'free'
    BUSY = 'busy'
    READY = 'ready'


class ASSIGNMENT_MESSAGE_TYPE(str, Enum):
    EXECUTION = 'assignment_execution'


class INSTANT_ACTIONS_TYPE(str, Enum):
    CANCEL = 'assignment_cancel'
    WPCLEREANCE = 'wp_clearance_request'  # AT MOMENT USED TO RESERVE
    RESERVE = 'reserve_for_mission'  # IT WILL SUBSTITUTE WPCLEREANCE
    RELEASE = 'release_from_mission'


class AGENT_MESSAGE_TYPE(str, Enum):
    MISSION = 'mission_request'
    STATE = 'agent_state'
    SENSORS = 'agent_sensors'
    UPDATE = 'agent_update'
    CHECKIN = 'checkin'


# ---- DATA MODELS ------ #


@dataclass
class AgentCurrentResources:
    operation_types_available: List[str]
    work_process_id: int
    reserved: bool


@dataclass
class AssignmentCurrentStatus:
    id: str
    status: ASSIGNMENT_STATUS
    result: dict


@dataclass
class AgentStateBody:
    status: AGENT_STATE
    resources: AgentCurrentResources
    assignment: AssignmentCurrentStatus


@dataclass
class AssignmentMetadata:
    id: int = 0
    work_process_id: int = 0
    yard_id: int = 0
    status: str = ASSIGNMENT_STATUS.TO_EXECUTE.value
    start_time_stamp: float = datetime.now()
    context: dict = field(default_factory=dict)


@dataclass
class WorkProcessResourcesRequest:
    work_process_id: int
    operation_types_required: List[str] = field(default_factory=list)
    reserved: bool = False


# -------- Agent Data ------------ #
@dataclass
class Pose:
    x: float = 0
    y: float = 0
    z: float = 0
    orientations: List[float] = field(default_factory=list)


# not used in the code, fields must be optional
@dataclass
class AgentCheckinData:
    name: str = ''
    code: str = ''
    factsheet: dict = field(default_factory=dict)
    pose: Pose = Pose
    data_format: str = ''
    is_actuator: bool = True
    unit: str = 'mm'


# ----   Messages From Agent to helyOS ------ #

@dataclass_json
@dataclass
class AgentStateMessage:
    uuid: str
    body: AgentStateBody
    type: AGENT_MESSAGE_TYPE = AGENT_MESSAGE_TYPE.STATE.value
    _version = VERSION


@dataclass_json
@dataclass
class MissionRequestMessage:
    uuid: str
    body: dict
    type: AGENT_MESSAGE_TYPE = AGENT_MESSAGE_TYPE.MISSION.value
    _version = VERSION


# ----   Messages From helyOS to Agent ------ #

@dataclass
class CheckinResponseMessage:
    uuid: str
    body: dict
    _version: str = ''
    type: AGENT_MESSAGE_TYPE = AGENT_MESSAGE_TYPE.CHECKIN.value
    metadata: dict = field(default_factory=dict)


@dataclass
class AssignmentCommandMessage:
    uuid: str
    body: dict
    _version: str = ''
    type: ASSIGNMENT_MESSAGE_TYPE = ASSIGNMENT_MESSAGE_TYPE.EXECUTION.value
    metadata: AssignmentMetadata = field(default_factory=dict)


@dataclass
class AssignmentCancelMessage:
    uuid: str
    body: dict
    _version: str = ''
    type: INSTANT_ACTIONS_TYPE  = INSTANT_ACTIONS_TYPE.CANCEL.value
    metadata: AssignmentMetadata = field(default_factory=dict)



@dataclass
class WorkProcessClearanceMessage:
    type = str
    uuid: str
    body: WorkProcessResourcesRequest
    _version: str = ''
    metadata: AssignmentMetadata = field(default_factory=dict)

