#!/usr/bin/env python3
import os
import sys

import arrow
import praw
import requests
import yaml
from prawcore.exceptions import RequestException, NotFound
from requests.exceptions import HTTPError

""" 
Customization Configuration

"""
# Default post_id: #
username = 'GallowBoob'

# Path to which to output the file #
# output_file_path = './'
# The Path to the stylesheet, relative to where the html file will be stored #
path_to_css = 'css/style.css'

"""
Reddit Post Archiver
By Samuel Johnson Stoever
"""

if len(sys.argv) == 1:
    print('No username was provided. Using default username.')
elif len(sys.argv) > 2:
    print('Too Many Arguments. Using default username.')
else:
    username = sys.argv[1]
username = username.rstrip('/')
if '/u/' in username:
    username = username.split('/u/')[1]
elif '/user/' in username:
    username = username.split('/user/')[1]

print('Processing all posts submitted by', username)
cred_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.yml')
credentials = yaml.load(open(cred_path))

r = praw.Reddit(client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                user_agent=credentials['user_agent'])


def get_user_post_id_set(user, first_id, postcount):
    user_post_id_set = set()
    if first_id is not None:
        params = dict(after=first_id, count=postcount)
        postgenerators = user.submissions.new(params=params)
    else:
        postgenerators = user.submissions.new()
    try:
        for post in postgenerators:
            post_id = "{}\n".format(post.id)
            user_post_id_set.add(post_id)
            postcount += 1
            if postgenerators.yielded == 100:
                try:
                    first_id = postgenerators.params['after']
                except KeyError:
                    first_id = None
    except NotFound:
        print('User not found with Reddit API.  Most likely deleted.')

    return user_post_id_set, first_id, postcount


def get_reddit_submissions(reddituser):
    try:
        user = r.redditor(reddituser)
    except HTTPError:
        print('Unable to write post ids: Invalid username or login credentials')
        return
    first_id = None
    postcount = 0
    try:
        user_post_id_set, first_id, postcount = get_user_post_id_set(user, first_id, postcount)
    except RequestException:
        return
    post_id_set = user_post_id_set
    subnumber = len(user_post_id_set)
    print("Received", subnumber, "posts from", reddituser)
    totalsubnumber = subnumber
    while subnumber > 99:
        try:
            user_post_id_set, first_id, postcount = get_user_post_id_set(user, first_id, postcount)
        except RequestException:
            break
        subnumber = len(user_post_id_set)
        totalsubnumber += subnumber
        post_id_set |= user_post_id_set
        print("Received additional", subnumber, "posts from Reddit for", reddituser, " -  Total posts received so far:",
              totalsubnumber, "with", len(post_id_set), "in set.")
    return post_id_set


def get_push_submissions(reddituser):
    push_post_id_set = set()
    now = arrow.utcnow().timestamp
    linktemplate = "https://api.pushshift.io/reddit/search/submission/?author={author}" \
                   "&before={timestamp}&sort=desc&size=500"
    url = linktemplate.format(author=reddituser, timestamp=now)
    rp = requests.get(url)
    push = rp.json()
    earliest = now
    subnumber = len(push['data'])
    totalsubnumber = 0
    print("Received", subnumber, "pushshift.io posts from", reddituser)
    while subnumber > 0:
        totalsubnumber += subnumber
        itemlist = push['data']
        push['data'] = list()
        for item in itemlist:
            if item['created_utc'] < earliest:
                earliest = item['created_utc']
            post_id = "{}\n".format(item['id'])
            push_post_id_set.add(post_id)
        url = linktemplate.format(author=reddituser, timestamp=earliest)
        rp = requests.get(url)
        push = rp.json()
        subnumber = len(push['data'])
        print("Received additional", subnumber, "posts from", reddituser, " -  Total posts received so far:",
              totalsubnumber, "with", len(push_post_id_set), "in pushshift.io set.")
    return push_post_id_set


def main():
    reddit_post_id_set = get_reddit_submissions(username)
    push_post_id_set = get_push_submissions(username)
    post_id_set = reddit_post_id_set.union(push_post_id_set)
    print("Total posts submitted by", username, "in set:", len(post_id_set))

    filedate = arrow.now().timestamp
    basedir = "/rpa" if os.environ.get('DOCKER', '0') == '1' else '.'
    output_file_path = "{basedir}/{username}_{timestamp}.txt".format(basedir=basedir, username=username, timestamp=filedate)

    with open(output_file_path, 'w', encoding='UTF-8') as post_file:
        post_file.writelines(post_id_set)


if __name__ == '__main__':
    main()
