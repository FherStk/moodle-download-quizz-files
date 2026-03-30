import os
import sys
import requests
from bs4 import BeautifulSoup
import zipfile
from urllib.parse import unquote
import configparser

def load_configuration():
    config_file = 'config.ini'
    
    if not os.path.exists(config_file):
        print(f"ERROR: The file '{config_file}' was not found.")
        print("Please create a config.ini file in this directory with your credentials.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_file)

    try:
        login_url = config['CREDENTIALS']['login_url']
        username = config['CREDENTIALS']['username']
        password = config['CREDENTIALS']['password']
        destination_folder = config['PATHS']['destination_folder']
        
        return login_url, username, password, destination_folder
    except KeyError as e:
        print(f"ERROR in config.ini: Missing parameter {e}")
        sys.exit(1)

def download_and_extract(login_url, username, password, destination_folder, quiz_url):
    session = requests.Session()

    print("\nLogging into Moodle...")
    try:
        r_login = session.get(login_url)
        r_login.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to the login URL: {e}")
        return

    soup_login = BeautifulSoup(r_login.text, 'html.parser')
    
    token_input = soup_login.find('input', {'name': 'logintoken'})
    logintoken = token_input['value'] if token_input else ''

    payload = {
        'username': username,
        'password': password,
        'logintoken': logintoken
    }
    session.post(login_url, data=payload)

    print("Accessing the quiz...")
    r_quiz = session.get(quiz_url)
    
    if "Identificarse" in r_quiz.text or "Log in" in r_quiz.text or "Acceso" in r_quiz.text:
        print("Error: Could not log in. Check your credentials in config.ini.")
        return

    soup_quiz = BeautifulSoup(r_quiz.text, 'html.parser')

    answers = soup_quiz.find_all('h4')
    answers = [node for node in answers if "Attempt number" in node.text]

    names = []
    files = []
    for a in answers:
        name = a.text.split(" for ")[1]
        file = a.next.next.find_all('a', href=True)
        file = [a['href'] for a in file if 'pluginfile.php' in a['href']]

        names.append(name)
        files.append(file)
    
    n = sum(len(f) for f in files)
    if n == 0:
        print("No files found. Please verify the quiz responses URL.")
        return

    print(f"Found {n} files. Starting download process...")
    
    os.makedirs(destination_folder, exist_ok=True)

    for student, download_url in zip(names, files):
        if(len(download_url) == 0): continue

        student_folder = os.path.join(destination_folder, student)
        os.makedirs(student_folder, exist_ok=True)

        file_name_url = download_url[0].split('/')[-1]
        file_name = unquote(file_name_url).split('?')[0]         
        file_path = os.path.join(student_folder, file_name)

        try:
            r_file = session.get(download_url[0], stream=True)
            with open(file_path, 'wb') as f:
                for chunk in r_file.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if file_name.lower().endswith('.zip'):
                file_folder = file_name[:-4]  # Remove the .zip extension
                student_folder = os.path.join(student_folder, file_folder)
                
                os.makedirs(student_folder, exist_ok=True)
                
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(student_folder)
                
                os.remove(file_path) 
                print(f"Downloaded and extracted: {file_path}")
            else:
                print(f"Downloaded: {file_path}")
                
        except zipfile.BadZipFile:
            print(f"ERROR: The file {file_path} is a corrupted ZIP and cannot be extracted.")
        except Exception as e:
            print(f"ERROR with {file_path}: {e}")

    print("-" * 30)
    print(f"Process finished. Check the folder: {destination_folder}")

if __name__ == "__main__":
    login_url, username, password, destination_folder = load_configuration()
    
    print("--- Moodle Quiz Downloader (v1.0.0) ---")
    quiz_url = ""
    while not quiz_url.strip():
        quiz_url = input("Paste the quiz responses URL (manual grading) and press Enter: ")

    download_and_extract(login_url, username, password, destination_folder, quiz_url)