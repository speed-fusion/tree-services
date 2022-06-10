import base64
from pathlib import Path
import time
import requests
import json

from pathlib import Path
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from datetime import datetime

from playwright_driver import PlaywrightDriver

import logging

class GmailAutomation:
    def __init__(self) -> None:
        
        self.cwd = Path.cwd()
        
        self.config_dir = self.cwd.joinpath("config")
        
        self.logs_dir = self.cwd.joinpath("logs")
        
        if not self.logs_dir.exists():
            self.logs_dir.mkdir()
            
        self.log_file = self.logs_dir.joinpath("log.txt")
        
        logging.basicConfig(filename= self.log_file, filemode='a',level=logging.INFO, format='%(process)d - %(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
        
        if not self.config_dir.exists():
            self.config_dir.mkdir()
        
        self.scopes = [
            "https://mail.google.com/"
        ]
        
        self.cred = None
        
        self.gmail_service = None
        
        self.labels = {}
        
        self.target_label = "auto_form_submit"
        
        self.subject_keywords = ['auto run','new lead']
        
        self.from_email = "thetreeservicepros@gmail.com"
        
        self.driver = PlaywrightDriver()
        
        self.google_sheet_endpoint = "https://script.google.com/macros/s/AKfycbxeP7qASKLN44D1mIGCUsHwZTsf6jK0n8jCflQjz4rZzN5VHikJhIba9EsNgNNLPugodw/exec"
    
    def load_credential(self):
        
        token_file = self.config_dir.joinpath("token.json")
        credential_file = self.config_dir.joinpath("credentials.json")
        
        if not credential_file.exists():
            print(f'{credential_file} does not exists.')
            return False

        if token_file.exists():
            self.cred = Credentials.from_authorized_user_file(token_file,self.scopes)
            return True
        
        if not self.cred or self.cred.valid:
            if self.cred and self.cred.expired and self.cred.refresh_token:
                self.cred.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credential_file,self.scopes)
                
                self.cred = flow.run_local_server(port=0)
            
            with open(token_file,"w") as token:
                token.write(self.cred.to_json())
            
            return True
        else:
            return False
    
    def build_gmail_service(self):
        
        self.gmail_service = build('gmail','v1',credentials=self.cred)
    
    def init_labels(self):
        res = self.gmail_service.users().labels().list(userId="me").execute()
        
        labels =  res.get("labels",[])
        
        for label in labels:
            self.labels[label["name"]] = label
        
    
    def get_new_emails(self):
        
        emails = []
        
        if not self.target_label in self.labels:
            print(f'please create label -> {self.target_label}')
            return
        label = self.labels[self.target_label]["id"]
        messages = self.gmail_service.users().messages().list(userId='me',labelIds=[label]).execute().get("messages",[])
        
        
        for message in messages:
            mail = self.gmail_service.users().messages().get(userId='me',id=message["id"]).execute()
            
            emails.append(mail)
            
            self.remove_label(label,message["id"])
            
        return emails
    
    
    def remove_label(self,label_id,message_id):
        msg_labels =  {'removeLabelIds': [label_id,'UNREAD'], 'addLabelIds': []}

        message = self.gmail_service.users().messages().modify(userId='me', id=message_id,
                                                    body=msg_labels).execute()
    
    def extract_html_soup(self,email):
        soup = None
        print(email)
        # for item in email["payload"]["parts"]:
        #     if item["mimeType"] == "text/html":
        body = email["payload"]["body"]["data"]
        decoded_bytes = base64.urlsafe_b64decode(body)
        string = str(decoded_bytes,"utf-8")
        soup = BeautifulSoup(string,features="html.parser")
                # break
        return soup
        
    def extract_incoming_email_address(self,email):
        mail_address = None
        
        for item in email["payload"]["headers"]:
            if item["name"] == "From":
                mail_address = item["value"]
                
                if "<" in mail_address:
                    mail_address = mail_address.split("<")[-1].split(">")[0].strip()
                
                break
        return mail_address

    def extract_subject(self,email):
        subject = None
        
        for item in email["payload"]["headers"]:
            if item["name"] == "Subject":
                subject = item["value"]                
                break
        return subject
    
    
    def extract_required_data_from_email_body(self,email):
        
        soup = self.extract_html_soup(email)
        
        email_from = self.extract_incoming_email_address(email)
        
        form_link = soup.find("a").get("href")
        
        if form_link != None:
            form_link = str(form_link).strip()
        
        subject = self.extract_subject(email)
        
        return {
            "email_from":email_from,
            "form_link":form_link,
            "subject":subject,
            "status":self.is_valid_email(subject,email_from)
        }
    
    def is_valid_email(self,subject,email_from):
        count = 0
        
        if email_from != self.from_email:
            return False
        
        for keyword in self.subject_keywords:
            if keyword in subject.lower():
                count += 1
        
        if count == 0:
            return False
        else:
            return True
    
    def init(self):
        if self.load_credential() == False:
            print(f'something went wrong...')
            return False
        
        self.build_gmail_service()
        
        self.init_labels()
    
    def submit_form(self,data):
        status = False
        
        try:
            self.driver.page.goto(data["form_link"])
            time.sleep(10)
            status = True
        except Exception as e:
            print(f'error : {str(e)}')
            
        return status

    def insert_row_in_google_sheet(self,data):
        
        payload = json.dumps(data)
        
        headers = {
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", self.google_sheet_endpoint, headers=headers, data=payload)
    
    def main(self):
        
        self.init()
        
        self.driver.start()
        
        for email in self.get_new_emails():
            
            data = self.extract_required_data_from_email_body(email)
            
            if data["status"] == False:
                continue
            
            
            status = self.submit_form(data)
            
            date_time = datetime.now()
            current_date_time = date_time.strftime("%d/%m/%Y %H:%M")
        
            row = {
            "timestamp": current_date_time,
            "link": data["form_link"],
            "subject":data["subject"],
            "email": data["email_from"],
            "status":status
                }
            
            logging.info(row)
            
            # self.insert_row_in_google_sheet(row)
            
        self.driver.stop()

if __name__ == "__main__":
    
    g = GmailAutomation()
    
    while True:
        g.main()
        time.sleep(30)