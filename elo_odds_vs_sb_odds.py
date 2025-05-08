import requests
import numpy as np
import pandas as pd

api_key = '<put_api_key_here>'
sport = 'icehockey_nhl'
regions = 'us'
markets = 'h2h'
odds_format = 'american'
date_format = 'iso'

print("Getting odds from sportsbooks...")
odds_response = requests.get('https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds', params={
    'api_key': api_key,
    'regions': regions,
    'markets': markets,
    'oddsFormat': odds_format,
    'dateFormat': date_format,
})

if odds_response.status_code != 200:
    print("Error getting odds")

else:
    odds_json = odds_response.json() #gets odds and puts into json
    odds_string_list = [str(i) for i in odds_json]
    with open("odds.json", "w") as file:
        file.write('\n'.join(odds_string_list) + '\n')
    init_df = pd.DataFrame(odds_json)
    print("Remaining API requests:", odds_response.headers['x-requests-remaining'])
    print("Used API requests:", odds_response.headers['x-requests-used'])

#df = pd.read_csv("odds.csv")

odds_df = init_df[['bookmakers']]
odds_df = odds_df.astype(str)
odds_df = odds_df['bookmakers'].str.split(",", expand=True)

def get_sb_odds(sb):
    sportbook=f" 'title': '{sb}'"
    find_sb=np.where(odds_df==sportbook) #Find where sportsbook data is in the dataframe
    sb_t1_odds=[]
    for i,j in zip(find_sb[0],find_sb[1]):
        j=j+5
        odd=odds_df.iloc[i,j]
        odd=odd.replace(" 'price': ", '')
        odd=odd.replace('}', '')
        odd=odd.replace(']', '')
        sb_t1_odds.append(odd)
    sb_t2_odds=[]
    for i,j in zip(find_sb[0],find_sb[1]):
        j=j+7
        odd=odds_df.iloc[i,j]
        odd=odd.replace(" 'price': ", '')
        odd=odd.replace('}', '')
        odd=odd.replace(']', '')
        sb_t2_odds.append(odd)
    return(sb_t1_odds,sb_t2_odds)

df=pd.DataFrame()
df['Team1']=odds_df.iloc[:,5]
df['Team2']=odds_df.iloc[:,7]

#clean data, this is horrific and could probably be a few lines but nothing is working and im over it
df['Team1']=df['Team1'].str.replace("'outcomes': [", '')
df['Team1']=df['Team1'].str.replace("{'name': ", '')
df['Team1']=df['Team1'].str.replace("'", '')
df['Team1']=df['Team1'].str.lstrip()
df['Team2']=df['Team2'].str.replace("{'name': ", '')
df['Team2']=df['Team2'].str.replace("'", '')
df['Team2']=df['Team2'].str.lstrip()

sportsbooks=['DraftKings']
sb_odd_names=[]
for i in sportsbooks:
    t1_odd,t2_odd=get_sb_odds(i)
    df[f'{i}_Team1_odds']=pd.Series(t1_odd)
    df[f'{i}_Team2_odds']=pd.Series(t2_odd)
    df[f'{i}_Team1_odds']=pd.to_numeric(df[f'{i}_Team1_odds'], errors='coerce')
    df[f'{i}_Team2_odds']=pd.to_numeric(df[f'{i}_Team2_odds'], errors='coerce')
    sb_odd_names.append(f'{i}_Team1_odds')
    sb_odd_names.append(f'{i}_Team2_odds')

df=df.dropna() #drop rows that are missing odds in any game

#convert odds from betting odds to %
for name in sb_odd_names:
    podds_list = []
    for i in df[name]:
        if i>0:
            podd=100/(i+100)
            podds_list.append(podd)
        elif i<0:
            podd=abs(i/(100-i))
            podds_list.append(podd)
        #append list of % odds to dataframe
    df[name + '%']=podds_list

#import elo data from google sheet
print("Importing Elo data...")
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow,Flow
from google.auth.transport.requests import Request
import os
import pickle

SCOPES=['https://www.googleapis.com/auth/spreadsheets']
SAMPLE_SPREADSHEET_ID='<put_spreadsheet_id_here>'
SAMPLE_RANGE_NAME='<put_data_range_here>'

def main():
    global values_input, service
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES) # here enter the name of your downloaded JSON file
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result_input = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range=SAMPLE_RANGE_NAME).execute()
    values_input = result_input.get('values', [])

    if not values_input and not values_expansion:
        print('No data found.')

main()

elo_df=pd.DataFrame(values_input[1:], columns=values_input[0])

#extract team elo rankings from elo_df
Team1_elos = []
for i in df['Team1']:
    elo=elo_df['Elo'][elo_df[elo_df['Team'] == i].index.tolist()].tolist()
    Team1_elos.extend(elo)

Team2_elos = []
for i in df['Team2']:
    elo=elo_df['Elo'][elo_df[elo_df['Team'] == i].index.tolist()].tolist()
    Team2_elos.extend(elo)

#convert elo values to floats
Team1_elos=[float(x) for x in Team1_elos]
Team2_elos=[float(x) for x in Team2_elos]
df['Team1_elos']=Team1_elos
df['Team2_elos']=Team2_elos

#calculate elo win% chance
print("Calculating win chances from Elo...")
df['Team1_elo%']=1/(1+10**((df['Team2_elos']-df['Team1_elos'])/400))
df['Team2_elo%']=1-df['Team1_elo%']

#compare elo odds to sb odds
print("Finding undervalued teams...")
hits=[]
for sb in sportsbooks:
    sb_hits=[]
    for i,j in zip(df['Team1_elo%'],df[f'{sb}_Team1_odds%']):
        if i>=j:
            uv_team=df['Team1'][df[df['Team1_elo%'] == i].index.tolist()].tolist()
            sb_hits.extend(uv_team)
    for i,j in zip(df['Team2_elo%'],df[f'{sb}_Team2_odds%']):
        if i>=j:
            uv_team=df['Team2'][df[df['Team2_elo%'] == i].index.tolist()].tolist()
            sb_hits.extend(uv_team)
    hits.append(sb_hits)

#make a final, presentable dataframe
final_df=df[['Team1', 'Team2', 'Team1_elo%', 'Team2_elo%']].copy()
for sb in sportsbooks:
    final_df[f'{sb}_Team1_odds%']=df[f'{sb}_Team1_odds%']
    final_df[f'{sb}_Team2_odds%']=df[f'{sb}_Team2_odds%']

#write email
print("Writing email...")
import datetime
from tabulate import tabulate

#the upcoming code is horrible from a security POV but I use a burner email for this so yolo
email_addresses = "<comma_separated_recipients>"
todays_date = datetime.date.today()
todays_date = str(todays_date)
email_subject = "Elo odds for " + todays_date
email_body = "Hello!\n\nI hope your day is going well so far. If any teams are listed, some sportsbooks may be undervaluing them; meaning the listed teams' win chance calculated from thier Elo rank is greater than that given to them by the sportsbook. Check the full dataset to compare these odds and make your own judgement call.\n\n"
for sb,h in zip(sportsbooks,hits):
    add_hit_text=f"If you use {sb}, you may want to bet on the following teams:\n\n" + str(h) + "\n\n"
    email_body = email_body + add_hit_text
email_body = email_body + "Below, you can find the calculated win chances based off both mini's Elo ratings, as well as the implied win chance from the sportsbooks' betting odds. Chances are reported as odds in decimal format (1 = 100%, 0.5 = 50%, etc.). Sportsbook odds may not add up to 100% because the house always wins... TLDR: Boosting both teams odds skews the odds in such a way that the house tends to keep more than it pays out.\n\n" + tabulate(final_df,headers='keys',tablefmt='psql') + "\n\nIf you choose to gamble, please do so responsibly."

#send email
print("Preparing to send email...")
from pyvirtualdisplay import Display
from selenium import webdriver
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def send_proton_email(email_to, email_subject, email_message):
    driver = ''
    display = ''
    try:
        display = Display(visible=0, size=(1920, 1080))   # Used to create a virtual display to be able to run selenium in a terminal without GUI
        display.start()
        driver = webdriver.Firefox()
        driver.get('https://account.proton.me/mail')
        print("Logging in to ProtonMail...")
        driver.find_element(By.ID,'username').send_keys('<login_email>')
        driver.find_element(By.ID,'password').send_keys('<password>') #so secure
        driver.find_element(By.XPATH,'/html/body/div[1]/div[4]/div[1]/main/div[1]/div[2]/form/button').click()
        sleep(3)
        #driver.find_element(By.ID,'password').send_keys('Mail_Decrypt_Password')
        #driver.find_element(By.ID,'unlock_btn').click()
        sleep(12)
        print("Creating new email...")
        driver.find_element(By.XPATH,'/html/body/div[1]/div[3]/div/div[2]/div/div[1]/div[2]/button').click()
        sleep(2)
        print('Writing recipient(s)...')
        driver.find_element(By.XPATH, '/html/body/div[1]/div[4]/div/div/div/div/div/div[2]/div/div/span/button[2]').click()
        driver.find_element(By.XPATH, '/html/body/div[1]/div[4]/div/div/div/div/div/div[2]/div[2]/div/div/div/div/input').send_keys(email_to)
        print('Writing subject and body text...')
        driver.find_element(By.XPATH, '/html/body/div[1]/div[4]/div/div/div/div/div/div[3]/div/div/input').send_keys(email_subject + Keys.TAB + email_message)
        #print('body')
        #driver.find_element(By.XPATH, '/html/body/div[1]/div/div[1]/div[1]').send_keys(email_message)
        sleep(0.5)
        driver.find_element(By.XPATH, '/html/body/div[1]/div[4]/div/div/div/footer/div/div[1]/button[1]').click()
        sleep(5)
        driver.quit()
        display.stop()
        print('E-mail Sent!')
        del email_subject
        del email_message
        del driver
        del display
    except Exception as err:
        driver.quit()
        display.stop()
        print('Error Occurred while sending e-mail!!')
        status = (str(err), 'Error Origin: Proton Mail Script')
        print(status)
        del err
        del status
        del driver
        del display

send_proton_email(email_addresses, email_subject, email_body)

print("Script complete")
