import hashlib
import hmac
import json
from flask import Flask, request, jsonify
from bot import config, github, env, gitlab, bump, version, rebase, cliq
from waitress import serve

app = Flask(__name__)

username = config.get_config('username')
email = config.get_config('email')
token = config.get_config('token')
hosting = config.get_config('hosting')
if hosting == "gitlab":
    host = config.get_config('host')
changelog_begin = config.get_config('changelog_begin')
changelog_end = config.get_config('changelog_end')
bearer_token = config.get_config('bearer_token')


def sha1_generate_signature(key, data):
    key_bytes = bytes(key, 'utf-8')
    data_bytes = bytes(data, 'utf-8')
    my_return = hmac.new(key_bytes, data_bytes, hashlib.sha1).hexdigest()
    return my_return


@app.route('/status', methods=['GET'])
def starting_url():
    return "Bot is running", 201


@app.route('/bot_bump_version', methods=['POST'])
def bot_bump_version():
    # verify_token_gitlab = request.headers.get('X-Gitlab-Token')
    # header_signature = request.headers.get('X-Hub-Signature')
    # if header_signature is None:
    #     return jsonify({'status': 'bad token'}), 401
    # sha_name, signature = header_signature.split('=')
    # if sha_name != 'sha1':
    #     return jsonify({'status': 'bad token'}), 401
    #
    # hashed = sha1_generate_signature(bearer_token, request.data)
    #
    # if verify_token_gitlab == bearer_token or str(hashed) == str(signature):
    #     pass
    # else:
    #     return jsonify({'status': 'bad token'}), 401
    try:
        request_data = json.loads(request.data)
        if hosting == "github":
            if not github.check_pull_request(request_data, username):
                return str("Just ignore"), 405
            if request_data['action'] == "assigned":
                repo = request_data['repository']['full_name']
                url = github.get_repo_url(token, request_data)
                branch = request_data['pull_request']['head']['ref']
                pull_request_url = request_data['pull_request']['html_url']
                pull_request_id = request_data['number']
                bot_command = branch.split('/')[0]
                owner = request_data['pull_request']['user']['login']
                changelog_message = request_data['pull_request']['body']
                default_branch = request_data['pull_request']['head']['repo']['default_branch']
            elif request_data['action'] == "created":
                repo = request_data['repository']['full_name']
                url = github.get_repo_url(token, request_data)
                pull_request_url = request_data['issue']['html_url']
                pull_request_id = request_data['issue']['number']
                branch = github.get_branch_name(token, repo, pull_request_id)
                bot_command = request_data['comment']['body'].split(' ')[1]
                owner = request_data['issue']['user']['login']
                changelog_message = request_data['issue']['body']
                try:
                    bot_command_2 = request_data['comment']['body'].split(' ')[2]
                except:
                    pass
                try:
                    bot_command_3 = request_data['comment']['body'].split(' ')[3]
                except:
                    pass
                default_branch = request_data['issue']['repository']['default_branch']
        elif hosting == "gitlab":
            object_kind = gitlab.object_kind(request_data)
            if not object_kind:
                return str("Just ignore"), 405
            if object_kind == "merge_request":
                merge_request_id = gitlab.get_assigne_mr_id(request_data, username)
                if not merge_request_id:
                    return str("Just ignore it is not merge_request"), 405
                url = gitlab.get_repo_url(token, request_data)
                branch = request_data['object_attributes']['source_branch']
                project_id = request_data['project']['id']
                merge_request_url = request_data['object_attributes']['url']
                bot_command = branch.split('/')[0]
                changelog_message = request_data['object_attributes']['description']
                default_branch = request_data['project']['default_branch']
            elif object_kind == "note":
                merge_request_id = gitlab.get_note_mr_id(request_data, username)
                if not merge_request_id:
                    return str("Just ignore it is not note"), 405
                url = gitlab.get_repo_url(token, request_data)
                branch = request_data['merge_request']['source_branch']
                project_id = request_data['project']['id']
                merge_request_url = request_data['merge_request']['url']
                bot_command = request_data['object_attributes']['note'].split(' ')[1]
                changelog_message = request_data['merge_request']['description']
                try:
                    bot_command_2 = request_data['object_attributes']['note'].split(' ')[2]
                except:
                    pass
                try:
                    bot_command_3 = request_data['object_attributes']['note'].split(' ')[3]
                except:
                    pass
                default_branch = request_data['project']['default_branch']

            assignee_merge_request_url = \
                'https://{}/api/v4/projects/{}/merge_requests/{}'.format(host,
                                                                         project_id, merge_request_id)

        command_list = ["rebase", "merge", "ft", "minor", "fix", "patch", "major", "help"]

        if bot_command not in command_list:
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id,
                                   str("Not correct command"))
            elif hosting == "gitlab":
                gitlab.send_answer(assignee_merge_request_url, token,
                                   str("Not correct command"))
            return str("Not correct command"), 405

        programming_language = env.get_microservice_lang(url)
        if not programming_language:
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id,
                                   "Could not find programming language in my list")
                github.re_assigne_owner(token, repo, pull_request_id,
                                        username, owner)
            elif hosting == "gitlab":
                gitlab.re_assigne_owner(assignee_merge_request_url,
                                        token, request_data)
                gitlab.send_answer(assignee_merge_request_url, token,
                                   "Could not find programming language in my list")
            return str(programming_language), 405

        setting_dict = config.get_version_setting(programming_language)
        if not setting_dict:
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id,
                                   "Could not find programming language in my list")
                github.re_assigne_owner(token, repo, pull_request_id,
                                        username, owner)
            elif hosting == "gitlab":
                gitlab.re_assigne_owner(assignee_merge_request_url,
                                        token, request_data)
                gitlab.send_answer(assignee_merge_request_url, token,
                                   "Could not find programming language in my list")
            return str("setting_dict error " + setting_dict), 405

        master_version_dict = version.get_master_version_dict(url, setting_dict)
        if not master_version_dict:
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id,
                                   "master_version_dict error")
                github.re_assigne_owner(token, repo, pull_request_id,
                                        username, owner)
            elif hosting == "gitlab":
                gitlab.re_assigne_owner(assignee_merge_request_url,
                                        token, request_data)
                gitlab.send_answer(assignee_merge_request_url, token,
                                   "master_version_dict error")
            return str("master_version_dict error"), 405

        old_version_dict = version.get_old_version_dict(url, setting_dict, branch)
        if not old_version_dict:
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id,
                                   "old_version_dict error")
                github.re_assigne_owner(token, repo, pull_request_id,
                                        username, owner)
            elif hosting == "gitlab":
                gitlab.re_assigne_owner(assignee_merge_request_url,
                                        token, request_data)
                gitlab.send_answer(assignee_merge_request_url, token,
                                   "old_version_dict error")
            return str("old_version_dict error"), 405

        if bot_command == "rebase":
            if bot_command_2 in command_list:
                # adding new function (check branch name and get default branch name)
                bot_command_3 = bot_command_2
                bot_command_2 = default_branch
            else:
                pass

            new_version_dict = version.get_new_version_dict(master_version_dict, bot_command_3)
            if not new_version_dict:
                if hosting == "github":
                    github.send_answer(token, repo, pull_request_id,
                                       "new_version_dict error")
                    github.re_assigne_owner(token, repo, pull_request_id,
                                            username, owner)
                elif hosting == "gitlab":
                    gitlab.re_assigne_owner(assignee_merge_request_url,
                                            token, request_data)
                    gitlab.send_answer(assignee_merge_request_url, token,
                                       "new_version_dict error")
                return str("new_version_dict error"), 405

            response_bump_version = rebase.bump_version_rebase(url, branch, setting_dict, new_version_dict,
                                                               username, email, bot_command_2)
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id, str(response_bump_version))
                github.re_assigne_owner(token, repo, pull_request_id, username, owner)
            elif hosting == "gitlab":
                gitlab.send_answer(assignee_merge_request_url, token, str(response_bump_version))
                gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)

            if "My friend, Adding a new commit was success" in response_bump_version:
                return str(response_bump_version), 200
            else:
                return str(response_bump_version), 405
        elif bot_command == "merge":
            if bump.check_bump_or_not(url, branch, setting_dict, old_version_dict, master_version_dict):
                pass
            else:
                if hosting == "github":
                    github.send_answer(token, repo, pull_request_id,
                                       "Could not merge. Please bump version before merge. \
                                       And dont forget add changelog in description")
                elif hosting == "gitlab":
                    gitlab.send_answer(assignee_merge_request_url, token,
                                       "Could not merge. Please bump version before merge. \
                                       And dont forget add changelog in description")
                return str("Could not merge"), 405

            if hosting == "github":
                if not github.merge_pull_request(token, repo, pull_request_id):
                    github.send_answer(token, repo, pull_request_id,
                                       "Could not merge for more information \
                                       please look at in webhook config")
                    github.re_assigne_owner(token, repo, pull_request_id, username, owner)
                    return str("Could not merge " + pull_request_url), 405
                else:
                    github.send_answer(token, repo, pull_request_id, "Merge was success")
                    github.re_assigne_owner(token, repo, pull_request_id, username, owner)
                    return str("Merge was Success"), 200
            elif hosting == "gitlab":
                if not gitlab.merge_request(assignee_merge_request_url, token):
                    gitlab.send_answer(assignee_merge_request_url, token,
                                       "Could not merge for more information \
                                       please look at in webhook config")
                    gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)
                    return str("Could not merge " + merge_request_url), 405
                else:
                    gitlab.send_answer(assignee_merge_request_url, token, "Merge was success")
                    gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)
                    return str("Merge was Success"), 200

        elif bot_command == "help":
            if hosting == "github":
                developer_mr = pull_request_url
            elif hosting == "gitlab":
                developer_mr = merge_request_url

            if config.get_config('cliq'):
                cliq_client_id = config.get_config('cliq_client_id')
                cliq_client_secret = config.get_config('cliq_client_secret')
                cliq_refresh_token = config.get_config('cliq_refresh_token')
                cliq_channel_name = config.get_config('cliq_channel_name')
                cliq_access_token = cliq.get_access_token(cliq_refresh_token, cliq_client_id, cliq_client_secret)

                if cliq.send_message(developer_mr, cliq_access_token, cliq_channel_name):
                    if hosting == "github":
                        github.send_answer(token, repo, pull_request_id, str("We'll get back to you in a few minutes"))
                        github.re_assigne_owner(token, repo, pull_request_id, username, owner)
                    elif hosting == "gitlab":
                        gitlab.send_answer(assignee_merge_request_url, token,
                                           str("We'll get back to you in a few minutes"))
                        gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)

                cliq.revoke_token(cliq_access_token)
            else:
                if hosting == "github":
                    github.send_answer(token, repo, pull_request_id, str("This bot dont has any chat integration"))
                    github.re_assigne_owner(token, repo, pull_request_id, username, owner)
                elif hosting == "gitlab":
                    gitlab.send_answer(assignee_merge_request_url, token, str("This bot dont has any chat integration"))
                    gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)

        else:
            new_version_dict = version.get_new_version_dict(master_version_dict, bot_command)
            if not new_version_dict:
                if hosting == "github":
                    github.send_answer(token, repo, pull_request_id,
                                       "new_version_dict error")
                    github.re_assigne_owner(token, repo, pull_request_id,
                                            username, owner)
                elif hosting == "gitlab":
                    gitlab.re_assigne_owner(assignee_merge_request_url,
                                            token, request_data)
                    gitlab.send_answer(assignee_merge_request_url, token,
                                       "new_version_dict error")
                return str("new_version_dict error"), 405

            response_bump_version = bump.bump_version(url, branch, setting_dict, old_version_dict,
                                                      new_version_dict, master_version_dict,
                                                      username, email, changelog_message,
                                                      changelog_begin, changelog_end)
            if hosting == "github":
                github.send_answer(token, repo, pull_request_id, str(response_bump_version))
                github.re_assigne_owner(token, repo, pull_request_id, username, owner)
            elif hosting == "gitlab":
                gitlab.send_answer(assignee_merge_request_url, token, str(response_bump_version))
                gitlab.re_assigne_owner(assignee_merge_request_url, token, request_data)

            if request.args.get('merge'):
                if hosting == "github":
                    if not github.merge_pull_request(token, repo, pull_request_id):
                        github.send_answer(token, repo, pull_request_id,
                                           "Could not merge for more information \
                                           please look at in webhook config")
                        return str("Could not merge " + pull_request_url), 405
                elif hosting == "gitlab":
                    if not gitlab.merge_request(assignee_merge_request_url, token):
                        gitlab.send_answer(assignee_merge_request_url, token,
                                           "Could not merge for more information \
                                           please look at in webhook config")
                        return str("Could not merge " + merge_request_url), 405

            if "My friend, Adding a new commit was success" in response_bump_version:
                return str(response_bump_version), 200
            else:
                return str(response_bump_version), 405
    except Exception as error:
        return str(error), 405


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)
