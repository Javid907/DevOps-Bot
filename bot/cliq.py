import requests
import json


def get_refresh_token():
    pass


def get_access_token(cliq_refresh_token, cliq_client_id, cliq_client_secret):
    try:
        query_url = "https://accounts.zoho.com/oauth/v2/token?refresh_token={}&client_id={}&client_secret={}&grant_type=refresh_token".format(
            cliq_refresh_token, cliq_client_id, cliq_client_secret)
        response = requests.post(query_url)
        data = response.json()
        return data['access_token']
    except Exception as error:
        return error


def revoke_token(cliq_access_token):
    try:
        query_url = "https://accounts.zoho.com/oauth/v2/token/revoke?token={}".format(cliq_access_token)
        response = requests.post(query_url)
        data = response.json()
        return data
    except Exception as error:
        return error


def send_message(developer_mr, cliq_access_token, cliq_channel_name):
    try:
        query_url = "https://cliq.zoho.com/api/v2/channelsbyname/{}/message".format(cliq_channel_name)
        headers = {'Authorization': "Bearer {}".format(cliq_access_token)}
        body = "Please look at this merge request need your help: {}".format(developer_mr)
        data = {"text": body}
        requests.post(query_url, data=json.dumps(data), headers=headers)
        return True
    except Exception as error:
        return error
