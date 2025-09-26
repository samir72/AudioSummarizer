import os
def retrieve_file_path(file_name):
    path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(path, file_name)
    if os.path.isfile(file_path):
        return file_path
    elif not os.path.exists(file_path):
        print(f"'{file_path}' does not exist.")
        return None
    return None