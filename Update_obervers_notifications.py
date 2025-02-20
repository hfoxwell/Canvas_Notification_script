import concurrent.futures  # For creating threadpool for multithreading users
import logging  # Logging tool for writing output to file
import logging.handlers  # Logging handlers for stdout printing
import threading
import os
import sys  # Operating system endpoints
import time  # Time library for measuring performance
from itertools import chain  # Iteration tool for iterating complex lists

from dotenv import load_dotenv
import requests  # Networking library for python
from canvasapi import account  # Canvas API Library for python
from canvasapi import Canvas, course, exceptions

#############################################################################################
## Configuration Options
#############################################################################################

# Load environment variables
env_file_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_file_path)

TERM_IDS = sys.argv[1].split(",")  # Read Term IDs from Command line input
API_URL = os.environ.get("CANVAS_URL")  # Assign API URL from Configuration file
API_KEY = os.environ.get("CANVAS_API_KEY")  # Assign API KEY from Configuration file

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

MAX_THREADS = 20  # Number of threads to use in multithreading
FILE_LOCK = threading.Lock()  # Locks the log file for writing

#############################################################################################
## Custom Exceptions
#############################################################################################

class BaseNotifierException(Exception):
    """Base exception for the script"""

class ForbiddenResourceException(BaseNotifierException):
    """Forbidden to access the provided resource"""


class APIConnectionException(BaseNotifierException):
    """Cannot connect to the API"""


class APIResourceUnavailableException(BaseNotifierException):
    """The resource requested through the API is not available"""


class APITimeOutException(BaseNotifierException):
    """API has timed out"""


class InvalidConfigurationException(BaseNotifierException):
    """Invalid configuration for canvas"""


class CanvasAccountException(BaseNotifierException):
    """An error retrieving the Nominated account"""


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
    except (exceptions.CanvasException, Warning) as canvas_exception:
        rootLogger.exception("Fatal Error creating Canvas connection.")
        rootLogger.exception(canvas_exception)
        rootLogger.exception("Ensure that your API key is valid")
        rootLogger.exception(
            "Ensure that your api reference does not contain 'api/v1/'"
        )
        exit()
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
    except (
        exceptions.BadRequest,
        exceptions.Unauthorized,
        exceptions.Forbidden,
        exceptions.ResourceDoesNotExist,
        exceptions.UnprocessableEntity,
    ) as canvas_exception:
        rootLogger.exception(
            "There was an error retrieving user account: %s", canvas_exception
        )
        raise

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

    def threaded_courses(chosen_course) -> list[int]:
        course_observer_ids = get_course_user_ids(chosen_course, user_type)
        rootLogger.info(
            f'{"-":^10}{chosen_course.name :<50} : {len(course_observer_ids) :>5} {user_type}'
        )
        return course_observer_ids

    # Iterate over all courses, find users of nominated type
    # add these users to a large list of users
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = executor.map(threaded_courses, all_courses)
        
    for result in results:
        all_user_ids = result + all_user_ids

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

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:
        futures = [
            executor.submit(
                submit_user_for_change, id, canvas_instance, notification_setting
            )
            for id in user_list
        ]

        # Execute the futures which are being processed
        concurrent.futures.wait(futures)


def submit_user_for_change(
    user_id: int, canvas_instance: Canvas, notification_setting: str
):
    """Function which prints information about current user,
    then sends the user's account for the notification settings to be changed.

    Args:
        user_id (int): _description_
    """
    # Variables
    start_time = time.time()
    user = canvas_instance.get_user(user_id)
    canvas_output: list[str] = []

    canvas_output. append(
        f"{'-':^10}{user.name} (ID: {user.id})"
    )
    canvas_output.append("-" * 60)

    # For this user, update all their notification preferences
    output = update_user_notification_preferences(user, notification_setting)

    for text in output:
        canvas_output.append(
            text
        )

    canvas_output.append(
        f"User change time: {time.time() - start_time} seconds\n" + "=" * 60
    )
    
    for output in canvas_output:
        with FILE_LOCK:
            rootLogger.info(
                output
            )



def update_user_notification_preferences(user, desired_preference) -> list[str]:
    """
    For each user gathers the communication channels which they are subscribed to, then
    updates their communication preferences with the selected communication preference.
    These preferences are found in NOTIFICATION_OPTIONS
    """

    # Variables
    text_output: list[str] = []
    channels: user = user.get_communication_channels()
      
    for channel in channels:
        # Append output to output list
        text_output.append(f"{'-':^10} {channel}")

        # Get the notification preferences for a channel
        try:
            response = requests.get(
                f"{API_URL}api/v1/users/{user.id}/communication_channels/{channel.id}/notification_preferences",
                headers=HEADERS,
                timeout=(TIMEOUT_SECONDS["in"], TIMEOUT_SECONDS["out"]),
            )
        except (
            requests.exceptions.Timeout,  # Request times out
            requests.exceptions.ProxyError,  # Proxy settings preventing channel aquisition
            requests.exceptions.HTTPError,  # Http error occured during channel aquisition
        ) as user_channel_error:
            rootLogger.error(
                "An error occured retrieving notification preferences for:%s's - %s channel.",
                user.name,
                channel,
            )
            rootLogger.exception(user_channel_error)

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
                text_output.append(f"{'-':^10}{'No Preferences to update.':<45}")
                return text_output

            # Create thread executor and create pool of execution threads
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(preferences)
            ) as submission_executor:
                submission_futures = [
                    submission_executor.submit(
                        send_to_canvas, user, desired_preference, channel, preference
                    )
                    for preference in preferences
                ]
            
                # Run all futures
                concurrent.futures.wait(submission_futures)
            
            # Retrieve all results from threads
            for future in submission_futures:
                text_output.append(future.result())

            text_output.append("All updates sent.")
    
    # Return all text outputs
    return text_output


def send_to_canvas(user, desired_preference, channel, preference) -> str:
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
    except (
        requests.exceptions.Timeout,  # Request times out
        requests.exceptions.ProxyError,  # Proxy settings preventing channel aquisition
        requests.exceptions.ConnectionError,  # Connection is lost
    ) as update_settings_error:
        rootLogger.exception(
            "An error occured with the requests module preventing settings update"
        )
        rootLogger.exception(update_settings_error)
        return

    return f'{"-":^10}{preference["notification"]:<45}{"=> " + desired_preference:>10} ( {"OK" if response.ok else f"FAILED - {response.status_code}"} )'


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
    print(os.getenv("API_URL"))

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
    all_users = get_user_ids(courses_in_term, ENROLLMENT_TYPES[int(chosen_enrolment)])
    all_users = remove_duplicates(all_users)

    # Iterate over users and update their notification settings
    iterate_users(canvas_instance, all_users, NOTIFICATION_OPTIONS[int(chosen_notification_option)])

    # Show end of program
    rootLogger.info(
        "Program completed, and took: %f seconds", time.time() - program_start
    )


if __name__ == "__main__":
    main()
