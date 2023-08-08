import csv
from datetime import datetime
import os 


class DataManager:
    def __init__(self, file_path):
        self.file_path = file_path

    def write_data(self, date, resources, enfants, email, phone, name):
        with open(self.file_path, 'a', newline='') as f:
            writer = csv.DictWriter(f,  fieldnames=['date','adultes','enfants','mail', 'tel', 'nom'])
            date = date.strftime('%d-%m-%Y %H:%M:%S')
            writer.writerow({'date':date, 'adultes':resources, 'enfants':enfants, 'mail':email, 'tel':phone, 'nom':name})


    def read_data(self):
        data = []
        try:
            with open(self.file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row:  # Skip empty rows
                        data.append(row.values())
        except FileNotFoundError:
            with  open('data_day.csv','w+')  as f:
                writer = csv.DictWriter(f, fieldnames=['date','adultes','enfants','mail', 'tel', 'nom'])
                writer.writeheader()
        return data

    def add_data_to_all_data_file(self):
        a = True
        if os.path.isfile('all_data.csv'):
            a = False
        with open('all_data.csv', 'a+', newline='') as all_data_file:
            writer = csv.DictWriter(all_data_file,  fieldnames=['date','adultes','enfants','mail', 'tel', 'nom'])
            if a:
                writer.writeheader()
            with open(self.file_path, 'r') as current_day_file:
                reader = csv.DictReader(current_day_file)
                for row in reader:
                    if row:  # Skip empty rows
                        writer.writerow(row)

