from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime, timedelta, time
from stockage_donnees import DataManager
import pandas as pd 
from pandas.tseries.offsets import DateOffset
import plotly.express as px
import plotly.offline as po
import os
import csv
import requests
from collections import defaultdict
from matplotlib.colors import Normalize
from matplotlib import cm

app = Flask(__name__)
data_manager = DataManager('data_day.csv')


############ Fonctions d'aide 
MAX_RESOURCES = 60
MAX_RESOURCES_PER_HOUR = 20


def resa_max_baudards(fichier, date, categorie): # categorie : adultes ou enfants
    df = pd.read_csv(fichier)
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y %H:%M:%S',  dayfirst=True)

    start_time = date - DateOffset(hours=3)
    end_time = date 
    in_use = df[(df['date'] >= start_time) & (df['date'] < end_time)][categorie].sum() 
    return in_use

def resa_max_creneau(fichier, date):
    df = pd.read_csv(fichier)
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y %H:%M:%S', dayfirst=True)
    #mask = (df['date'].year == date.year and df['dat-%m'].hour == date.hour and df['date'].min == date.min)
    #df_filtered = df.loc[mask]
    df_filtered = df[df['date'] == date]
    total = df_filtered['adultes'].sum() + df_filtered['enfants'].sum()
    print(total)
    print(f"date : {date}")
    return total

def scale(val, src, dst):
    return ((val - src[0]) / (src[1]-src[0])) * (dst[1]-dst[0]) + dst[0]


def generate_calendar(year, month):
    # Create a list of half-hour time slots
    times = [f"{h:02d}:{m:02d}" for h in range(9, 19) for m in [0, 30]]

    # Create the range of dates for the month
    start_date = datetime(year, month, 1)
    end_date = (start_date + pd.DateOffset(months=1)) - timedelta(days=1)
    dates = pd.date_range(start_date, end_date)
    dates = dates.strftime('%d-%m-%Y')
    # Import the CSV data
    df = pd.read_csv('all_data.csv')

    # Convert the 'Date' column to datetime and set it as index
    df['Date'] = pd.to_datetime(df['date'], format="%d-%m-%Y %H:%M:%S", dayfirst=True) 
    df.set_index('Date', inplace=True)
    df['time'] = df.index.time
    
    df['total'] = df['adultes'] + df['enfants']
    
    # Create a new DataFrame with multi-index
    multi_index = pd.MultiIndex.from_product([dates, ['adultes', 'enfants', 'total']], names=['Date', 'Nb clients'])
    original_calendar = pd.DataFrame(index=multi_index, columns=times)
    original_calendar.fillna(0, inplace=True) # fill all cells with 0

    # Update the calendar DataFrame with the data from the CSV
    for date, room in original_calendar.index:
        date_as_datetime = pd.to_datetime(date, dayfirst=True)
        for time in times:
            hour, minute = map(int, time.split(':'))
            mask = (df.index.day == date_as_datetime.day) & (df.index.month == date_as_datetime.month) & (df.index.hour == hour) & (df.index.minute == minute)
            current_sum = df.loc[mask, room].values.sum()
            for i in range(6):  # Extend over the next 3 hours
                try:
                    original_calendar.loc[(date, room), times[times.index(time) + i]] += current_sum
                except IndexError:
                    break  # We're at the end of the times list
  
    # Create a new DataFrame and add rows from the original DataFrame and blank rows
    calendar_with_blanks = pd.DataFrame()
    
    blank_counter = 0
    for date in dates:
        daily_data = original_calendar.loc[pd.IndexSlice[date, :], :]
        blank_row = pd.DataFrame(index=pd.MultiIndex.from_tuples([(f"---- Fin jour : {blank_counter +1} ---- ", " ")]), columns=original_calendar.columns)
        blank_row.fillna('', inplace=True) # fill all cells with empty string
        calendar_with_blanks = pd.concat([calendar_with_blanks, daily_data, blank_row])
        blank_counter += 1

    return calendar_with_blanks


def generate_and_style_calendar(year, month):
    # Generate calendar
    calendar = generate_calendar(year, month)

    # Create colormap
    color_map = cm.get_cmap('RdYlGn_r')

    # Apply color gradient
    styled = calendar.style.background_gradient(cmap=color_map, vmin=0, vmax=60, subset=pd.IndexSlice[:, 'adultes', :])\
                     .background_gradient(cmap=color_map, vmin=0, vmax=20, subset=pd.IndexSlice[:, 'enfants', :])\
                     .background_gradient(cmap=color_map, vmin=0, vmax=80, subset=pd.IndexSlice[:, 'total', :])

    return styled



############

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        date_str = request.form.get('date')  # should be in format 'YYYY-MM-DD HH:MM:SS'
        date = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
        resources = int(request.form.get('resources'))
        enfants = int(request.form.get('enfants'))
        email = request.form.get('email')
        phone = request.form.get('phone')
        name = request.form.get('name')
        
        
        in_use_all = resa_max_baudards('all_data.csv', date, 'adultes')
        in_use_day = resa_max_baudards('data_day.csv', date, 'adultes')

        warnings = []
        if in_use_all + resources + in_use_day  > MAX_RESOURCES:
            warnings.append(f"ATTTTTTENTTTIONNNNNNN ! Trop d'adultes sur la période (pas assez de bodars potentiellement) : {in_use_all + in_use_day}. On se charbonne la tronche ou pas ? ")

        
        creneau_all = resa_max_creneau('all_data.csv', date)
        creneau_jour = resa_max_creneau('data_day.csv', date)
        
        if creneau_all + creneau_jour + resources + enfants > MAX_RESOURCES_PER_HOUR:
            warnings.append(f"ATTTTTTENTTTIONNNNNNN ! Trop de personnes sur ce créneau spécifique (plus de {MAX_RESOURCES_PER_HOUR}) nombre de personnes {creneau_all + creneau_jour}.  On se charbonne la tronche ou pas ?")
        
        force = request.form.get('force', 'false') == 'true'
        
        if not warnings or force:
            data_manager.write_data(date, resources, enfants,  email, phone, name)

        if warnings and not force:
            return jsonify({'warnings': warnings}), 200
    
        return redirect(url_for('home'), code=303)
        
    
    # Reading data from CSV
    data = data_manager.read_data()
    # Convert data to list of dictionaries for HTML
    df = pd.DataFrame(data, columns=['date', 'resources', 'enfants', 'email', 'phone', 'name'])
    data_html = df.to_dict(orient='records')
    return render_template('index.html', data=data_html)
    
    

@app.route('/register', methods=['POST'])
def register():
    date_str = request.form.get('date')  # should be in format 'YYYY-MM-DD HH:MM:SS'
    date = datetime.strptime(date_str, '%d-%m-%Y %H:%M', dayfirst=True)
    resources = int(request.form.get('resources'))
    enfants = int(request.form.get('enfants'))
    email = request.form.get('email')
    phone = request.form.get('phone')
    name = request.form.get('name')
    
    # Writing data to CSV
    data_manager.write_data(date, resources, email, phone, name)
    return jsonify({'status': 'success'})

@app.route('/add_all_data', methods=['GET'])
def add_all_data():
    DataManager('data_day.csv').add_data_to_all_data_file()
    os.remove('data_day.csv')
    return redirect(url_for('home'))

@app.route('/view_histogram', methods=['GET'])
def view_histogram():
    # Read data from all_data.csv
    df = pd.read_csv('all_data.csv')

    # Convert the 'date' column to datetime
    df['date'] = pd.to_datetime(df['date'])

    # Filter rows from the current day
    df = df[df['date'].dt.date == datetime.today().date()]

    # Convert datetime to minutes after midnight
    df['minutes'] = df['date'].dt.hour * 60 + df['date'].dt.minute

    # Generate predefined bins from 09h30 to 18h (510 minutes range starting from 570 minutes after midnight)
    bins = range(570, 570 + 510+1, 30)  # Adjust the step size to your needs, e.g., 30 mins
    df['time_bins'] = pd.cut(df['minutes'], bins, include_lowest=True)

    df['Nb_resa'] = df['adultes'] + df['enfants']

    # Count the number of 'Nb_resa' in each time bin
    df_histogram = df.groupby('time_bins')['Nb_resa'].sum().reset_index()

    # Convert 'time_bins' to 'HH:MM' format to avoid serialization issues
    df_histogram['time_bins'] = df_histogram['time_bins'].apply(lambda x: str(timedelta(minutes=int(x.mid) + 15))[0:5])

    # Plot histogram
    fig = px.bar(df_histogram, x='time_bins', y='Nb_resa')

    # Convert the figure to HTML and include it in the template
    histogram_div = po.plot(fig, output_type='div')
    return render_template('histograms.html', histogram_div=histogram_div)



@app.route('/view_calendar', methods=['GET'])
def calendar():
    mois_actu = datetime.today().month
    calendar = generate_and_style_calendar(2023, mois_actu)
    return render_template('calendar.html', table=calendar.to_html())


if __name__ == "__main__":
    app.run(debug=True)
