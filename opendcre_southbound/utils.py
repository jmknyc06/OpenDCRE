#!/usr/bin/env python
""" Utility methods for OpenDCRE

    Author: Erick Daniszewski
    Date:   09/20/2016

    \\//
     \/apor IO

-------------------------------
Copyright (C) 2015-17  Vapor IO

This file is part of OpenDCRE.

OpenDCRE is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

OpenDCRE is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OpenDCRE.  If not, see <http://www.gnu.org/licenses/>.
"""
import errno
import json
import logging
import os
import threading
from Queue import Queue

from flask import current_app

from constants import device_name_codes, DEVICE_NONE
from errors import OpenDCREException

logger = logging.getLogger(__name__)


# -------------------------------------
# Board ID Utilities
# -------------------------------------

def board_id_to_hex_string(hex_value):
    """ Convenience method to convert a hexadecimal board_id value into its hex
    string representation, without the '0x' prefix, and with left-padding added
    if needed (for a 4 byte width).

    Args:
        hex_value (int): hexadecimal board id value.

    Returns:
        str: A string representation of the board id.
    """
    return '{0:08x}'.format(hex_value)


def board_id_to_bytes(board_id):
    """ Convert a hexadecimal board_id value into a corresponding list of bytes.

    Given a hex value, will convert the value to a hex string. If the value is
    not 4 bytes wide, padding will be added to the string to ensure correct size.
    The string is then split, converted back to a hexadecimal value and the four
    bytes are returned as a list.

      e.g. 0xAABBCCDD -> [AA, BB, CC, DD]
           0xFF       -> [00, 00, 00, FF]

    Args:
        board_id (str): the hexadecimal value representing the id of the board

    Returns:
        list[int]: A list, of length 4, comprising the individual bytes of the board id
    """
    if isinstance(board_id, (int, long)):
        return [int('{0:08x}'.format(board_id)[i:i + 2], 16) for i in range(0, 8, 2)]

    elif isinstance(board_id, (str, unicode)):
        board_id = int(board_id, 16)
        return [int('{0:08x}'.format(board_id)[i:i + 2], 16) for i in range(0, 8, 2)]

    elif isinstance(board_id, list) and len(board_id) == 4:
        return board_id

    else:
        raise TypeError('board_id type is unsupported: {}'.format(type(board_id)))


def board_id_join_bytes(board_id_bytes):
    """ Convert a list of individual bytes into their corresponding board_id value.

    Given a list of bytes (generated by board_id_to_bytes), joins the bytes into a
    single value (the original board_id value)

    Args:
        board_id_bytes (list[int]): a list of bytes (int) of the board id. this list must
            contain 4 bytes.

    Returns:
        int: A board_id value.
    """
    if not isinstance(board_id_bytes, list) or len(board_id_bytes) != 4:
        raise ValueError('board_id_bytes not of type list / not of length 4')

    byte1 = board_id_bytes[0] << 24
    byte2 = board_id_bytes[1] << 16
    byte3 = board_id_bytes[2] << 8
    byte4 = board_id_bytes[3]
    return byte1 + byte2 + byte3 + byte4


# -------------------------------------
# Device ID Utilities
# -------------------------------------


def device_id_to_hex_string(hex_value):
    """ Convenience method to convert a hexadecimal device_id value into its hex
    string representation, without the '0x' prefix, and with left-padding added
    if needed (for a 2 byte width).

    Args:
        hex_value (int): hexadecimal device id value.

    Returns:
        str: A string representation of the device id.
    """
    return '{0:04x}'.format(hex_value)


def device_id_to_bytes(device_id):
    """ Convert a hexadecimal device_id value into a corresponding list of bytes.

    Given a hex value, will convert the value to a hex string. If the value is
    not 2 bytes wide, padding will be added to the string to ensure correct size.
    The string is then split, converted back to a hexadecimal value and the two
    bytes are returned as a list.

      e.g. 0xAABB -> [AA, BB]
           0xFF   -> [00, FF]

    Args:
        device_id (str): the hexadecimal value representing the id of the device

    Returns:
        list[int]: A list, of length 2, comprising the individual bytes of the device id
    """
    if isinstance(device_id, (int, long)):
        return [int('{0:04x}'.format(device_id)[i:i + 2], 16) for i in range(0, 4, 2)]

    elif isinstance(device_id, (str, unicode)):
        device_id = int(device_id, 16)
        return [int('{0:04x}'.format(device_id)[i:i + 2], 16) for i in range(0, 4, 2)]

    elif isinstance(device_id, list) and len(device_id) == 2:
        return device_id

    else:
        raise TypeError('device_id type is unsupported: {}'.format(type(device_id)))


def device_id_join_bytes(device_id_bytes):
    """ Convert a list of individual bytes into their corresponding device_id value.

    Given a list of bytes (generated by device_id_to_bytes), joins the bytes into a
    single value (the original device_id value)

    Args:
        device_id_bytes (list[int]): a list of bytes (int) of the device id. this
            list must contain 2 bytes.

    Returns:
        int: A device_id value.
    """
    if not isinstance(device_id_bytes, list) or len(device_id_bytes) != 2:
        raise ValueError('device_id_bytes not of type list / not of length 2')

    byte1 = device_id_bytes[0] << 8
    byte2 = device_id_bytes[1]
    return byte1 + byte2


def get_device_type_code(device_type):
    """ Gets a numeric value corresponding to a string value describing a
    device type.

    Args:
        device_type (str): string value representing device type

    Returns:
        int: device type code. 0xFF if device_type is not recognized.
    """
    if device_type in device_name_codes:
        return device_name_codes[device_type]
    else:
        return device_name_codes[DEVICE_NONE]


def get_device_type_name(device_code):
    """ Gets a string value corresponding to a numeric code representing
    a device type.

    Args:
        device_code (int): the numeric device code value.

    Returns:
        str: device type name. 'none' if device_code is not recognized.
    """
    for name in device_name_codes:
        if device_name_codes[name] == device_code:
            return name
    return DEVICE_NONE


# -------------------------------------
# Validation Utilities
# -------------------------------------


def check_valid_board_and_device(board_id=None, device_id=None):
    """ Validate that the board and device IDs are valid for the operation, and
    convert from hex string to int value for each, if valid.

    Args:
        board_id (str): The board_id to check.
        device_id (str): The device_id to check.

    Returns:
        tuple[int, int]: a 2-tuple of ints for the converted board_id and device_id, in that order
    """
    board_id_int = check_valid_board(board_id)
    try:
        device_id_int = int(device_id, 16)
        if device_id_int < 0:
            raise ValueError('Device ID must be a positive numeric value.')
    except ValueError:
        # we still allow the process to proceed, as device_id may be the device_id string where applicable
        logger.debug('Error converting device_id to int: {}'.format(device_id))
        return board_id_int, device_id

    return board_id_int, device_id_int


def check_valid_board(board_id=None):
    """ Validate that the board id is valid for this operation, and convert from
    hex string to int value for each, if valid.

    Args:
        board_id (str): The board_id to check.

    Returns:
        int: an integer for the converted board_id
    """
    try:
        board_num_int = int(board_id, 16)
        if board_num_int > 0xFFFFFFFF or board_num_int < 0x00:
            raise ValueError('Board number {} specified is out of range.'.format(board_id))
    except ValueError:
        # we still allow the process to proceed, as board_id may be ip/hostname where applicable
        logger.debug('Error converting board_id to int: {}'.format(board_id))
        return board_id

    return board_num_int


# -------------------------------------
# Cache Utilities
# -------------------------------------


def get_scan_cache():
    """ Convenience method to get the scan cache, as a dictionary.

    Returns:
        dict: the scan cache. if no cache exists, an empty dictionary
            is returned.
    """
    cache_file = current_app.config['SCAN_CACHE']
    try:
        with open(cache_file, 'r') as f:
            cache = json.load(f)
    except (OSError, IOError):
        return {}
    return cache


def write_scan_cache(data):
    """ Write the given data to the scan cache.

    This method replaces the current scan cache with the given data. This
    method will not update (e.g. join) the existing data with the given
    data.

    Args:
        data (dict): the data to write to the cache file.
    """
    cache_file = current_app.config['SCAN_CACHE']
    _dir, _ = os.path.split(cache_file)
    try:
        os.makedirs(_dir)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(_dir):
            pass
        else:
            raise
    try:
        with open(cache_file, 'w+') as f:
            json.dump(data, f)
    except (OSError, IOError) as e:
        logger.error('Unable to write to cache file: {}'.format(cache_file))
        logger.exception(e)
        raise


# -------------------------------------
# Device Interface Utilities
# -------------------------------------

def get_device_instance(board_id):
    """ Get a device instance for a given board ID.

    This function first checks with all single-board devices for a matching instance,
    and if located, returns the device (which presumably can then be used to handle a
    command); if not found, then the range-devices are checked, and if the board_id
    falls within the given range, we return that device. If nothing is found, an
    OpenDCRE exception is raised.

    The board_id passed in here need not be just a board_id. Since we can do lookups
    based on the IP / hostname, the board_id may also be one of those.

    Args:
        board_id (str | int): the board_id to locate.

    Returns:
        DevicebusInterface: the desired device bus interface

    Raises:
        OpenDCREException: no device bus interface is found for the given board_id
    """
    logger.debug('get_device_instance board_id {}'.format(board_id))
    if board_id is None:
        raise OpenDCREException('Board ID must be specified in retrieving devicebus instance.')

    device = current_app.config['SINGLE_BOARD_DEVICES'].get(board_id, None)
    if device is not None:
        return device
    else:
        logger.debug('current_app.config[RANGE_DEVICES] {}'.format(current_app.config['RANGE_DEVICES']))

        for range_device in current_app.config['RANGE_DEVICES']:
            # Does this work for multiple range devices? It just returns the first one. (Code review)
            if range_device.board_id_range[0] <= board_id <= range_device.board_id_range[1]:
                return range_device

        raise OpenDCREException(
            'Board ID ({}) not associated with any registered devicebus handler.'.format(
                hex(board_id) if isinstance(board_id, int) else board_id
            )
        )


# -------------------------------------
# Threaded Registration Utilities
# -------------------------------------

# -----------------------------------------------------------------------------
# NOTE (etd 10/2016):
#
# With the addition of a threaded device registration for IPMI devices, this
# becomes necessary for pyghmi to operate properly within a spawned thread.
# in short, the reason for this is because importing a module within a
# thread (in python 2 -- this should not be a problem in python 3) creates
# a deadlock. to work around this, we need to ensure that all imports are
# done in the main thread prior to spawning any subsequent worker threads.
# the primary offender in the case of pyghmi is using various encode/decodes
# throughout which we do not use in opendcre core. as such, this loops through
# the known codecs being used in pyghmi in order to load them into the global
# cache so they are accessible to the threads without needing to cause
# deadlocking imports.
#
# of note:
#  * the 'idna' codec is used by socket.getaddrinfo, not by pyghmi directly.
#  * unicode('x', 'utf_8') is needed here, even though we are encoding to the
#    utf-8 codec as well. i am a bit unclear why this is. it appears that
#    'utf-8' is the default coding for unicode(), however removing the 'utf_8'
#    parameter causes issues, so i assume there are some under-the-hood
#    differences there that actually do matter.
#
# Please refrain from modifying / moving / removing this unless you really
# know what you are doing and what side effects you should expect by making
# those modifications.
# -----------------------------------------------------------------------------
def cache_registration_dependencies():
    """ Convenience method to cache pyghmi dependencies which may not already
    be present in OpenDCRE Southbound.

    This should be called prior to registering devices, specifically for IPMI,
    so that dependency import is not done in the thread, which causes a deadlock
    in Python 2
    """
    pyghmi_codecs = ['idna', 'utf-8', 'iso-8859-1', 'utf-16le']
    for codec in pyghmi_codecs:
        unicode('x', 'utf_8').encode(codec).decode(codec)


class Worker(threading.Thread):
    """ Worker thread executing tasks assigned in a tasks queue.
    """
    def __init__(self, tasks):
        super(Worker, self).__init__()
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            fn, args, kwargs = self.tasks.get()
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error('Failed to complete task:')
                logger.exception(e)
            finally:
                self.tasks.task_done()


class ThreadPool(object):
    """ Manages a task queue which is given to a pool of worker threads.
    """
    def __init__(self, thread_count):
        self.tasks = Queue(thread_count)
        for _ in xrange(thread_count):
            Worker(self.tasks)

    def add_task(self, fn, *args, **kwargs):
        """ Add a new task to the queue.

        Args:
            fn: method making up the task
            *args: arguments to the method
            **kwargs: keyword arguments to the method
        """
        self.tasks.put((fn, args, kwargs))

    def map(self, fn, args_list):
        """ Add a list of tasks to the queue.

        Args:
            fn: the method making up the task
            args_list: a list of arguments for the method
        """
        for args in args_list:
            self.add_task(fn, args)

    def wait_for_task_completion(self):
        """ Wait until all of the tasks in the queue have completed.
        """
        self.tasks.join()
