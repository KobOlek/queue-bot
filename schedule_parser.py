import json

def parse_json(filename: str) -> list:
    with open(filename, 'r') as sch_file:
        data = json.load(sch_file)

    final_data_list = []

    for subgroup, subject_dict in data.items():
        for subject_name, date_list in subject_dict.items():
            for date in date_list:
                final_data_list.append([subject_name, subgroup, date])

    return final_data_list