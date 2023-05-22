from collections import defaultdict
import csv
import numpy as np

def read_energy_mix_csv(file_path):
    monthly_energy_mix = []

    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        next(reader)  # Skip the first row with units

        for row in reader:
            total_energy = sum(float(row[key]) for key in row if key not in ['Monat'])

            energy_mix = {
                "coal": (float(row["Braunkohle"]) + float(row["Steinkohle"])) / total_energy,
                "natural_gas": float(row["Erdgas"]) / total_energy,
                "nuclear": float(row["Kernenergie"]) / total_energy,
                "renewable": (float(row["Laufwasser"]) + float(row["Biomasse"]) + float(row["Geothermie"]) +
                              float(row["Speicherwasser"]) + float(row["Wind Offshore"]) + float(row["Wind Onshore"]) +
                              float(row["Solar"])) / total_energy
            }
            monthly_energy_mix.append(energy_mix)

    return monthly_energy_mix


def read_hdd_csv(file_path):
        # Initialize a list with 12 zeros to store the heating degree days for each month with numpy
        monthly_hdd_sum = np.zeros(12)

        # Initialize a dictionary to store the count of records for each month
        monthly_hdd_count = defaultdict(int)

        with open(file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                next(reader)  # Skip the first row with units

        # Iterate through the CSV rows and accumulate the heating degree days for each month
                for row in reader:
                        year_month = row["TIME_PERIOD"]
                        month = year_month[-2:]
                        # convert string of month to int
                        month = int(month)-1
                        hdd = float(row["OBS_VALUE"])
                        monthly_hdd_sum[month] += hdd
                        monthly_hdd_count[month] += 1
        
        # Calculate the average heating degree days for each month
        return monthly_hdd_sum / np.array(list(monthly_hdd_count.values()))
        