import logging  # Logging tool for writing output to file
import logging.handlers  # Logging handlers for stdout printing
import os
import sys  # Operating system endpoints
import threading  # Multithreading tool for concurrent I/O operations
import time  # Time library for measuring performance
from itertools import chain  # Iteration tool for iterating complex lists

import dotenv
import requests  # Networking library for python
from canvasapi import (
    Canvas,
    account,  # Canvas API Library for python
    course,
    exceptions,
)

#############################################################################################
## Configuration Options
#############################################################################################

# Load environment variables
dotenv.load_dotenv()

TERM_IDS = sys.argv[1].split(",")  # Read Term IDs from Command line input
API_URL = os.getenv("CANVAS_URL")  # Assign API URL from Configuration file
API_KEY = os.getenv("CANVAS_API_KEY")  # Assign API KEY from Configuration file

HEADERS = {  # Headers to be included with each request
    "Content-type": "application/json",  # Data type to submit to Canvas
    "Authorization": f"Bearer {API_KEY}",  # Authorisation using API Key
}

TIMEOUT_SECONDS = {  # Timeouts for reading data in and out of a request
    "in": 5,
    "out": 5,
}

NOTIFICATION_OPTIONS = {  # Canvas notification options
    0: "never",  # NEVER notify
    1: "immediately",  # IMMEDIATELY notify
    2: "daily",  # DAILY summary notification
    3: "weekly",  # WEEKLY summary notification
}

ENROLLMENT_TYPES = {0: "observer"}  # Canvas user types  # Observer type user

EXCLUDED_NOTIFICATIONS = (  # Notification categories to exclude
    "confirm_sms_communication_channel",
    "account_user_notification",
)

CANVAS_ACCOUNT = os.getenv(
    "CANVAS_ACCOUNT"
)  # Canvas account for access level (DEFAULT => 1)

LOG_LEVEL = logging.INFO  # Set the logging level for the terminal and the logfile

#############################################################################################
## Custom Exceptions
#############################################################################################


class ForbiddenResourceException(Exception):
    pass


class APIConnectionException(Exception):
    pass


class APIResourceUnavailableException(Exception):
    pass


class APITimeOutException(Exception):
    pass


class InvalidConfigurationException(Exception):
    pass


#############################################################################################
# Configure the logger
# ===================
logFormatter = logging.Formatter(
    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
rootLogger = logging.getLogger(__name__)
rootLogger.setLevel(LOG_LEVEL)

fileHandler = logging.FileHandler("logfile.log")
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
rootLogger.addHandler(consoleHandler)
# ===================

#############################################################################################
## Functions
#############################################################################################


def connect_to_canvas(api_domain: str, api_key: str) -> Canvas:
    """
    Connects to canvas instance and returns an object which is able to
    gather data about users and courses.
    """

    # Print action to console
    rootLogger.info(f"Accessing: {api_domain}")
    rootLogger.info(f"Using API key {api_key}...\n")

    try:
        canvas = Canvas(api_domain, api_key)
    except exceptions.BadRequest as canvas_bad_request:
        rootLogger.exception("Fatal Error connecting to canvas: %s", canvas_bad_request)
        raise canvas_bad_request
    except exceptions.InvalidAccessToken as invalid_token:
        rootLogger.exception("Supplied API key is not valid: %s.", invalid_token)
        raise invalid_token
    except exceptions.Unauthorized as unauthorized:
        rootLogger.exception("User is unauthorised: %s", unauthorized)
        raise unauthorized
    except exceptions.Forbidden as forbidden:
        rootLogger.exception(
            "This user is forbidden from accessing this resource: %s", forbidden
        )
        raise forbidden
    except exceptions.ResourceDoesNotExist as resource_nonexistant:
        rootLogger.exception("Resource doesn't exist: %s", resource_nonexistant)
        raise resource_nonexistant

    return canvas


def get_account(canvas_connection: Canvas, account_number: int) -> account.Account:
    """
    Retrieves the main account from canvas for the script
    to use to access all courses for the given term.

    Raises:
        canvas_bad_request: _description_
        invalid_token: _description_
        unauthorized: _description_
        forbidden: _description_
        resource_nonexistant: _description_

    Returns:
        Account: Canvas user account
    """
    try:
        user_account: account.Account = canvas_connection.get_account(account_number)
    except exceptions.BadRequest as canvas_bad_request:
        rootLogger.exception("Fatal Error connecting to canvas: %s", canvas_bad_request)
        raise canvas_bad_request
    except exceptions.InvalidAccessToken as invalid_token:
        rootLogger.exception("Supplied API key is not valid: %s.", invalid_token)
        raise invalid_token
    except exceptions.Unauthorized as unauthorized:
        rootLogger.exception("User is unauthorised: %s", unauthorized)
        raise unauthorized
    except exceptions.Forbidden as forbidden:
        rootLogger.exception(
            "This user is forbidden from accessing this resource: %s", forbidden
        )
        raise forbidden
    except exceptions.ResourceDoesNotExist as resource_nonexistant:
        rootLogger.exception("Resource doesn't exist: %s", resource_nonexistant)
        raise resource_nonexistant

    return user_account


def display_term_ids(TERM_IDS):
    """
    Documents the term id's which are being operated on.
    """
    rootLogger.info("Accessing Term IDs:")
    for term_id in TERM_IDS:
        rootLogger.info(f"{'-':^10}{term_id}\n")


def get_courses_by_term_ids(canvas_account: account.Account):
    """
    Retrieves the courses in the given term, the courses which are accessed must be visible
    from the account which has been set by CANVAS_ACCOUNT. This is most effectual when an
    Admin account is used.
    """

    # Variables
    course_list: list[course.Course] = list()

    # Iterate over terms and retrieve a course
    # Expand out the list of courses for each term and concatenate to
    # the previous terms courses
    for term_id in TERM_IDS:
        course_list = list(
            chain(
                course_list,
                canvas_account.get_courses(per_page=500, enrollment_term_id=term_id),
            )
        )
    return course_list


def get_user_ids(all_courses: list[course.Course], user_type: str) -> list[int]:
    """
    For each course, finds and retrieves the user ID for each of the chosen user type.
    """

    # Variables
    all_user_ids = list()
    start_time = time.time()

    # Formatting for log file
    rootLogger.info("Courses\n" + "=" * 60)

    # Iterate over all courses, find users of nominated type
    # add these users to a large list of users
    for course in all_courses:
        course_observer_ids = get_course_user_ids(course, user_type)
        rootLogger.info(
            f'{"-":^10}{course.name :<50} : {len(course_observer_ids) :>5} {user_type}'
        )
        all_user_ids = all_user_ids + course_observer_ids

    rootLogger.info(
        f"Finished in: {time.asctime(time.localtime(time.time() - start_time)) :>20}"
    )

    return all_user_ids


def get_course_user_ids(canvas_course: course.Course, enrolment_type: str):
    """
    For a course, retrieve all users of a particular user type. These user types are
    defined in the ENROLMENT_TYPES.
    """
    course_user_ids = list()
    users = canvas_course.get_users(enrollment_type=enrolment_type)

    for user in users:
        course_user_ids.append(user.id)

    return course_user_ids


def remove_duplicates(user_list) -> set[int]:
    """
    Removes duplicate user ids from the list of users
    this is achieved by converting to set, which cannot have duplicates
    """
    return set(user_list)


def iterate_users(
    canvas_instance: Canvas, user_list: set[int], notification_setting: str
):
    """
    Iterates over the list and updates each user's notification settings
    """

    # Variables
    user_count = len(user_list)
    current_user = 0

    rootLogger.info(
        "\n"
        + "=" * 60
        + f"\n Total: {len(user_list)} observers"
        + "\n"
        + "=" * 60
        + "\n"
    )

    # Loop through all observers by ID
    for user_id in user_list:
        # Variables
        start_time = time.time()
        user = canvas_instance.get_user(user_id)

        # Increment current user count
        current_user += 1

        rootLogger.info(
            f"{current_user}/{user_count} - {user.name} (ID: {user.id})\n" + "-" * 60
        )

        # For this user, update all their notification preferences
        update_user_notification_preferences(user, notification_setting)

        rootLogger.info(
            f"User change time: {time.time() - start_time} seconds\n" + "=" * 60
        )


def update_user_notification_preferences(user, desired_preference):
    """
    For each user gathers the communication channels which they are subscribed to, then
    updates their communication preferences with the selected communication preference.
    These preferences are found in NOTIFICATION_OPTIONS
    """
    channels: user = user.get_communication_channels()
    for channel in channels:
        # Variables
        threads: list[threading.Thread] = list()
        rootLogger.info(f"{'-':^10} {channel}")
        # Get the notification preferences for a channel

        try:
            response = requests.get(
                f"{API_URL}api/v1/users/{user.id}/communication_channels/{channel.id}/notification_preferences",
                headers=HEADERS,
                timeout=(TIMEOUT_SECONDS["in"], TIMEOUT_SECONDS["out"]),
            )
        except exceptions.BadRequest as canvas_bad_request:
            rootLogger.exception(
                "Fatal Error connecting to canvas: %s", canvas_bad_request
            )
            raise canvas_bad_request
        except exceptions.InvalidAccessToken as invalid_token:
            rootLogger.exception("Supplied API key is not valid: %s.", invalid_token)
            raise invalid_token
        except exceptions.Unauthorized as unauthorized:
            rootLogger.error("User is unauthorised: %s", unauthorized)
        except exceptions.Forbidden as forbidden:
            rootLogger.error(
                "This user is forbidden from accessing this resource: %s", forbidden
            )
        except exceptions.ResourceDoesNotExist as resource_nonexistant:
            rootLogger.exception("Resource doesn't exist: %s", resource_nonexistant)

        else:
            preferences = response.json()["notification_preferences"]
            # Filter the preferences that don't match the desired_preference
            preferences = [
                pref
                for pref in preferences
                if pref["frequency"] != desired_preference
                and not (pref["notification"] in EXCLUDED_NOTIFICATIONS)
            ]

            if not (len(preferences) > 0):
                rootLogger.info(f"{'-':^10}{'No Preferences to update.':<45}")
                return

            for preference in preferences:
                thread = threading.Thread(
                    target=send_to_canvas,
                    args=(user, desired_preference, channel, preference),
                )
                threads.append(thread)

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            rootLogger.info("All updates sent.")


def send_to_canvas(user, desired_preference, channel, preference):
    """
    Sends the notification preference for a particular chanel to the Canvas server
    """
    payload = {"notification_preferences": [{"frequency": desired_preference}]}

    try:
        response = requests.put(
            f"{API_URL}api/v1/users/self/communication_channels/{channel.id}/notification_preferences/{preference['notification']}?as_user_id={user.id}",
            headers=HEADERS,
            json=payload,
            timeout=(TIMEOUT_SECONDS["in"], TIMEOUT_SECONDS["out"]),
        )
    except exceptions.BadRequest as canvas_bad_request:
        rootLogger.exception("Fatal Error connecting to canvas: %s", canvas_bad_request)
        raise canvas_bad_request
    except exceptions.InvalidAccessToken as invalid_token:
        rootLogger.exception("Supplied API key is not valid: %s.", invalid_token)
        raise invalid_token
    except exceptions.Unauthorized as unauthorized:
        rootLogger.exception("User is unauthorised: %s", unauthorized)
        raise unauthorized
    except exceptions.Forbidden as forbidden:
        rootLogger.exception(
            "This user is forbidden from accessing this resource: %s", forbidden
        )
        raise forbidden
    except exceptions.ResourceDoesNotExist as resource_nonexistant:
        rootLogger.exception("Resource doesn't exist: %s", resource_nonexistant)
        raise resource_nonexistant

    rootLogger.info(
        f'{"-":^10}{preference["notification"]:<45}{"=> " + desired_preference:>10} ( {"OK" if response.ok else f"FAILED - {response.status_code}"} )'
    )


#############################################################################################
## Main
#############################################################################################


def main():
    """Main function for the script, drives all other functions. 

    Raises:
        InvalidConfigurationException: 
            Signals that the configuration of the .env file is incorrect
    """

    # Variables
    program_start = time.time()
    chosen_notification_option = os.getenv("NOTIFICATION_OPTION")
    chosen_enrolment = os.getenv("ENROLMENT_OPTION")

    # Validate correct configuration
    if chosen_notification_option is None:
        raise InvalidConfigurationException(
            "No Notification has been chosen in the configuration file."
        )
    if chosen_enrolment is None:
        raise InvalidConfigurationException(
            "No user enrolment has been configured in the configuration file."
        )
    if API_KEY is None or API_URL is None:
        raise InvalidConfigurationException(
            "No API URL or API kEY specified, please check the configuration"
        )
    if CANVAS_ACCOUNT is None:
        raise InvalidConfigurationException(
            "No Canvas account chosen masquerading changes, check configuration."
        )

    # Output to user start of program
    rootLogger.info("Program start...")

    canvas_instance = connect_to_canvas(API_URL, API_KEY)
    admin_account = get_account(canvas_instance, int(CANVAS_ACCOUNT))

    # Print to user term information
    display_term_ids(TERM_IDS)

    # Load Courses and retrieve users from those courses
    # Remove duplicates from the list
    courses_in_term = get_courses_by_term_ids(admin_account)
    all_users = get_user_ids(courses_in_term, ENROLLMENT_TYPES[0])
    all_users = remove_duplicates(all_users)

    # Iterate over users and update their notification settings
    iterate_users(canvas_instance, all_users, NOTIFICATION_OPTIONS[0])

    # Show end of program
    rootLogger.info(
        "Program completed, and took: %f seconds", program_start - time.time()
    )


if __name__ == "__main__":
    main()
