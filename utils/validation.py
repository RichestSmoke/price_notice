import re

def check_input_notice_data(user_input):
    pattern = r'^[a-zA-Z]{2,6}-\d+\.\d+-(buy|sell|BUY|SELL|[BSbs])$'
    return bool(re.match(pattern, user_input))


def string_to_list(data):
    result_list = re.split(',|,', data)
    result_list = list(filter(None, result_list))
    return result_list