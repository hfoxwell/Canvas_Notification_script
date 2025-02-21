# Observer Notification Bulk set

With large sets of users added into canvas, it is possible that you have large counts of parent observers. The default settings for notifications is far too comprehensive, meaning that parents receive notifications for almost every activity on canvas. This is not desirable, particularly as default behavior. 

## Purpose of the script

This script changes the notification settings for user groups on canvas. The use case for my institution was to change the notification status of parent observers for canvas. Parents were being notified for every action on canvas, and possibly for multiple courses at the same time. 

The script iterated through all courses offered in a term, identified the observers, then changed their notification status to the desired setting. 

## Dependencies

This script relies on: 

 - Logging
 - Threading
 - OS
 - SYS
 - time
 - itertools
 - requests

 Externals:
 - [dotenv](https://pypi.org/project/python-dotenv/)
 - [canvasapi](https://canvasapi.readthedocs.io/en/stable/getting-started.html)

## Configuration options

### ENVIRONMENT FILE

The environment file contains basic configuration options which are set for the project. This file is loaded at he beginning of the program. Most important, is the `CANVAS_URL` and `CANVAS_API_KEY` these two constants direct the program to the canvas instance, and provides the API key for authentication. 

### Headers

Headers provided to canvas. These are standard and used with any request when made to canvas. This draws from the `.env` file.

### Timeout Seconds

Used to customise the timeout used by the requests module. If a request takes longer than the timeout, it will be considered a failed connection. **DEFAULTS** to 5 seconds

### Notification options

Python dictionary of notification options, allows for the user to customise what type of notifications are given to observers. Options are as follows:

- **Never**: Never notify
- **Immediately**: Notify user immediately
- **Daily**: daily summary notification
- **Weekly**: Weekly summary notification 

This dictionary is used to pick which option is provided to the API, it is set in the `.env` file. 

## Enrolment types

**NOTE this is subjective to your installation**
It is very likely that you have different enrolment types in your system. For the system this was deployed on, `observers` were the user type which was being targeted. Therefore, this was the only user type that was targeted. 
You might need to do more research on your own instance to ascertain what group of users you are targeting. You can then modify the dictionary to include these items.