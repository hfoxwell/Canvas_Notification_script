from canvasapi import Canvas
from itertools import chain
import threading
import requests
import json
import time
import sys

# Read login credentials
with open('config.json', 'r') as f:
	config = json.load(f)

TERM_IDS = sys.argv[1].split(',')
API_URL = f"{config['Test']['API_URL']}"
API_KEY = config['Test']['API_KEY']

HEADERS = {
	'Content-type': 'application/json',
	'Authorization': 'Bearer ' + API_KEY
}

NOTIFICATION_OPTIONS = {
	0 : "never",
	1 : "immediately",
	2 : "daily",
	3 : "weekly"
}

ENROLLMENT_TYPES = {
	0: "observer"
}

EXCLUDED_NOTIFICATIONS = (
	"confirm_sms_communication_channel",
	"account_user_notification"
)


def get_courses_by_term_ids(account):
	courses = list()
	for term_id in TERM_IDS:
		courses = list(chain(courses, account.get_courses(per_page=500, enrollment_term_id=term_id)))
	return courses


def get_course_observer_ids(course):
	course_observer_ids = list()
	course_observers = course.get_users(enrollment_type=ENROLLMENT_TYPES[0])

	for observer in course_observers:
		course_observer_ids.append(observer.id)
	
	return course_observer_ids

def send_to_canvas(user, desired_preference, channel, preference):
    payload = { "notification_preferences": [ {"frequency": desired_preference} ] }
    response = requests.put(API_URL + "api/v1/users/self/communication_channels/{}/notification_preferences/{}?as_user_id={}".format(channel.id, preference['notification'], user.id), headers = HEADERS, json = payload)
    print(f'{"-":^10}{preference["notification"]:<45}{"=> " + desired_preference:>10} ( {"OK" if response.ok else f"FAILED - {response.status_code}"} )')
   

def update_user_notification_preferences(user, desired_preference):
	channels = user.get_communication_channels()
	for channel in channels:
		print(f"\n - {channel} \n")
		
		# Get the notification preferences for a channel
		response = requests.get(
			f"{API_URL}api/v1/users/{user.id}/communication_channels/{channel.id}/notification_preferences", headers = HEADERS
		)
		preferences = response.json()['notification_preferences']
		# Filter the preferences that don't match the desired_preference
		preferences = [pref for pref in preferences if pref['frequency'] != desired_preference and not(pref['notification'] in EXCLUDED_NOTIFICATIONS)]
		
		if not(len(preferences) > 0):
			print("No Preferences to update.")
			return
		
		threads = []
		for preference in preferences:
			thread = threading.Thread(target=send_to_canvas, args=(user, desired_preference, channel, preference))
			threads.append(thread)
   
		for thread in threads:
			thread.start()
   
		for thread in threads:
			thread.join()
		
		print("All updates sent.")

try:
	# Attempt access with entered credentials
	print("\nAccessing {}".format(API_URL))
	print("with API key {}...\n".format(API_KEY))
	canvas = Canvas(API_URL, API_KEY)
	account = canvas.get_account(1)
except Exception as error:
		print(error)

else:
	
	all_observer_ids = list()
	print("Accessing Term IDs:")
	for term_id in TERM_IDS:
		print(f" - {term_id}\n")

	
	print("Courses\n" + "="*60)
	
	# Loop through all the courses
	courses = get_courses_by_term_ids(account)
	course_start_time = time.time()
	for course in courses:
		
		course_observer_ids = get_course_observer_ids(course)
		print(f'{"-":^10}{course.name :<50} : {len(course_observer_ids) :>4} observers')
		all_observer_ids = all_observer_ids + course_observer_ids
	print(f'Finished in: {time.asctime(time.localtime(time.time() - course_start_time)) :>20}')	
 
	# Remove duplicates/convert to set
	all_observer_ids = set(all_observer_ids)
	observers_num = len(all_observer_ids)
	print("\n" + "="*60 + "\n Total: {} observers".format(observers_num) + "\n" + "="*60 + "\n")
	
	# Loop through all observers by ID
	observer_count = 0
	for id in all_observer_ids:
		user_start_time = time.time()
		user = canvas.get_user(id)
		observer_count += 1
		print()
		print(f'{observer_count}/{observers_num} - {user.name} (ID: {user.id})\n')
		print('-' * 60)
		update_user_notification_preferences(user, NOTIFICATION_OPTIONS[0])
		print()
		print("User change time: {} seconds".format(time.time() - user_start_time))
		# print("Total runtime: {} seconds".format(time_since(program_start_time)))
		print()
		print("="*60)
