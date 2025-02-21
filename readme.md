# Observer Notification Bulk set

With large sets of users added into canvas, it is possible that you have large counts of parent observers. The default settings for notifications is far too comprehensive, meaning that parents receive notifications for almost every activity on canvas. This is not desirable, particularly as default behavior. 

## Purpose of the script

This script changes the notification settings for user groups on canvas. The use case for my institution was to change the notification status of parent observers for canvas. Parents were being notified for every action on canvas, and possibly for multiple courses at the same time. 

The script iterated through all courses offered in a term, identified the observers, then changed their notification status to the desired setting. 

## Contents

 - [Dependancies](#dependencies)
 - [Configuration Options](#configuration-options)
    - [Env file](#environment-file)
    - [Headers](#headers)
    - [Time Outs](#timeout-seconds)
    - [Notification Options](#notification-options)
    - [Enrolment Types](#enrolment-types)
    - [Excluded notifications](#excluded-notifications)
    - [Canvas Account](#canvas-account)
    - [Log levels](#log-levels)
    - [Max Threads](#max-threads)
 - [Command line arguments](#command-line-arguments)

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

### Enrolment types

**NOTE this is subjective to your installation**
It is very likely that you have different enrolment types in your system. For the system this was deployed on, `observers` were the user type which was being targeted. Therefore, this was the only user type that was targeted. 
You might need to do more research on your own instance to ascertain what group of users you are targeting. You can then modify the dictionary to include these items.

### Excluded notifications

This tuple of text values aligns with the notifications which you may wish to exclude from being affected. This can allow you to turn of or affect a particular subset of communications within the canvas system, and leave other more critical comms to the default behaviour. 

### Canvas account

As this system is usually performed from an admin perspective, within canvas, an account is needed for impersonation. The account chosen as a default `1`, is the admin account for the instance this was tested on; It may be different for your particular use case. This account needs to have access to the [term](https://canvas.instructure.com/doc/api/enrollment_terms.html) you are examining. For example, if you are deactivating notifications for 2024 Term 3 Senior school, then the impersonated account needs this access. To ensure this, impersonate the highest level admin account you have access or permission for. 

### Log levels

This allows you to set the different levels of logging. The **Default** is `INFO` which outputs only informational, and above, messages. This can be adjusted if you need more detail from logging, if `DEBUG` is chosen then the requests module may also emit messages. 

The options available are:
 - DEBUG
 - INFO
 - WARNING
 - ERROR
 - CRITICAL

### Max Threads 

If your program is causing your computer to melt down, or you are rate-limiting with canvas, this variable should be reduced. Generally, 10 threads is acceptable, and doesn't cause too much fuss on modern systems. 
This program is regularly run on an old (2015) i5 Processor, though it was developed on a modern macintosh. Depending on your setup you may need to suit this to your taste. 

## Command line arguments

