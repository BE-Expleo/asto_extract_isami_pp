#!/usr/bin/env python
# coding: utf-8


import os
from pathlib import Path
import warnings
import shutil

import pandas as pd
import numpy as np

warnings.simplefilter(action='ignore', category=FutureWarning)


def get_lc(lc_file):
    df_ulc = pd.read_excel(lc_file, sheet_name='ULC List', usecols=['LoadCase label', 'LoadCase ID'])
    df_ulc.rename(columns={"LoadCase label": "LC", "LoadCase ID": "LC_ID"}, inplace=True)
    nb_ulc = len(df_ulc)

    df_clc = pd.read_excel(lc_file, sheet_name='CLC List', usecols=['Combined LoadCase label', 'LC_no'])
    df_clc.rename(columns={"Combined LoadCase label": "LC", "LC_no": "LC_ID"}, inplace=True)
    list_clc_id = df_clc.LC_ID.values.tolist()

    df_lc = pd.concat([df_ulc, df_clc], axis=0, ignore_index=True)
    list_lc = df_lc.LC.values.tolist()

    return nb_ulc, list_clc_id, df_lc, list_lc


def list_criteria(df_result):
    criteria_list = list(df_result.columns)
    criteria_list.remove('FE')
    criteria_list.remove('LC')
    return criteria_list


def format_synthesis_right_area(df_result_row, criteria_list_to_keep):
    # Transpose
    df_result = df_result_row.T

    # Move first row to head
    df_result.columns = df_result.iloc[0]
    df_result = df_result.iloc[1:, :]

    # Change column index and rename in criteria
    df_result.reset_index(inplace=True)
    df_result.columns.name = None
    df_result.rename(columns={'index': 'Criteria'}, inplace=True)

    # Insert column FE
    df_result.insert(0, 'FE', '')
    df_result['FE'] = df_result.iloc[:, [2]].shift(periods=1)

    df_result['FE'] = np.where(df_result.Criteria != criteria_list_to_keep[0], '', df_result['FE'])

    # Remove lines FE
    df_result = df_result[df_result.Criteria != 'FE']
    df_result.reset_index(drop=True, inplace=True)

    # Insert column FEM element
    df_result.insert(0, 'FEM element', '')
    df_result['FEM element'] = df_result.iloc[:, [1]]

    # Insert element id's in rows for each criteria
    row_numbers = df_result[df_result['Criteria'] == criteria_list_to_keep[0]].index
    for i in row_numbers:
        # for j in range(i + 1, i + len(criteria_list)):
        for j in range(i + 1, i + len(criteria_list_to_keep)):
            df_result.loc[j, 'FEM element'] = df_result.loc[j - 1, 'FEM element']

    # Insert column Component
    df_result.insert(1, 'Component', '')
    df_result['Component'] = df_result['Criteria']
    return df_result


def create_synthesis_right_area(df_result, df_lc, criteria_list_to_keep):
    # Clean column Fe
    df_result['FE'] = df_result['FE'].str[5:]

    # List elements
    elm_list = df_result['FE'].unique()

    # Sort by LC
    df_result.sort_values(by=['LC'], inplace=True)

    # Merge df_result and df_lc
    df_result = pd.merge(df_lc, df_result)

    # Change LC and LC_ID column order
    columns_name = df_result.columns.tolist()
    columns_name[0], columns_name[1] = columns_name[1], columns_name[0]
    df_result = df_result.reindex(columns=columns_name)

    # Create a list of dataframes with results by elm
    df_result_elm_list = []

    for elm in elm_list:
        df_result_elm = df_result.query('FE == @elm').reset_index(drop=True)
        if elm != elm_list[0]:
            del df_result_elm["LC"]
            del df_result_elm["LC_ID"]
        df_result_elm_list.append(df_result_elm)

    # Concat in one df
    df_result_row = pd.concat(df_result_elm_list, axis=1)

    # Format synthesis right area
    df_result = format_synthesis_right_area(df_result_row, criteria_list_to_keep)

    return df_result


def add_synthesis_left_area(df_result, list_clc_id):
    df_result_clc_only_id = df_result[list_clc_id].copy()
    df_result_clc_only_id = df_result_clc_only_id.iloc[1:, :]
    df_result_clc_only_id = df_result_clc_only_id.astype(float)

    df_result_clc_only_lc_name = df_result[list_clc_id].copy()
    new_header = df_result_clc_only_lc_name.iloc[0]
    df_result_clc_only_lc_name = df_result_clc_only_lc_name[1:]
    df_result_clc_only_lc_name.columns = new_header
    df_result_clc_only_lc_name = df_result_clc_only_lc_name.astype(float)

    df_max_value = df_result_clc_only_id.max(axis=1)
    df_idmax = df_result_clc_only_id.idxmax(axis=1)
    df_lcmax = df_result_clc_only_lc_name.idxmax(axis=1)

    df_min_value = df_result_clc_only_id.min(axis=1)
    df_idmin = df_result_clc_only_id.idxmin(axis=1)
    df_lcmin = df_result_clc_only_lc_name.idxmin(axis=1)

    # Insert column Max, Max_LC_Name, Max_LC_ID
    df_result.insert(2, 'Max', df_max_value)
    df_result.insert(3, 'Max_LC_Name', df_lcmax)
    df_result.insert(4, 'Max_LC_ID', df_idmax)
    df_result.insert(5, 'Min', df_min_value)
    df_result.insert(6, 'Min_LC_Name', df_lcmin)
    df_result.insert(7, 'Min_LC_ID', df_idmin)
    return df_result


def create_synthesis(csv_result_file, nb_ulc, list_clc_id, df_lc, list_lc, criteria_list_to_keep):
    df_result = pd.read_csv(csv_result_file, usecols=lambda x: x != 'TableValues', sep=';', skiprows=range(0, 11))

    # List criteria
    criteria_list = list_criteria(df_result)
    print(f"extracted_criteria_list {criteria_list}")
    print(f"criteria_list_to_keep {criteria_list_to_keep}")
    criteria_list_to_del = [x for x in criteria_list if x not in criteria_list_to_keep]
    print(f"criteria_list_to_del {criteria_list_to_del}")

    for criteria in criteria_list_to_del:
        df_result.drop(criteria, axis=1, inplace=True)

    # Create right area of synthesis with LC in columns and criteria in rows for each element
    df_result = create_synthesis_right_area(df_result, df_lc, criteria_list_to_keep)

    # Add left area of synthesis with max and min values
    df_result = add_synthesis_left_area(df_result, list_clc_id)

    # Formatting
    # Formatting 2 first rows
    data_top_lc = df_result.columns.values.tolist()[:10] + list_lc
    data_top_lc_id = df_result.columns.values.tolist()
    for i in range(10):
        data_top_lc_id[i] = ""
    df_result.loc[0] = data_top_lc
    df_result = pd.DataFrame([data_top_lc_id], columns=df_result.columns).append(df_result)
    df_result = df_result.sort_index().reset_index(drop=True)

    # Insert columns
    df_result.insert(loc=0, column='empty0', value=['' for i in range(df_result.shape[0])])
    df_result.insert(loc=9, column='empty9', value=['' for i in range(df_result.shape[0])])
    df_result.insert(loc=10, column='empty10', value=['' for i in range(df_result.shape[0])])
    df_result.insert(loc=11 + 2 + nb_ulc, column='emptyCLC', value=['' for i in range(df_result.shape[0])])

    # Write xlsx file
    synthesis_file = f"{csv_result_file[:len(csv_result_file) - 4]}_synthesis.xlsx"
    with pd.ExcelWriter(synthesis_file, engine='xlsxwriter') as writer:
        df_result.to_excel(writer, sheet_name="Results", na_rep='', index=False, startrow=0, header=False)

    return df_result, criteria_list, synthesis_file


def create_transpose(df_result, nb_ulc, csv_result_file):
    # Create dataframe for transpose
    df_result_clc = df_result.copy()

    # Remove left columns and ULC
    df_result_clc = df_result_clc.drop(df_result_clc.iloc[:, :11], axis=1)
    df_result_clc.drop(df_result_clc.iloc[:, 2:nb_ulc + 3], axis=1, inplace=True)

    # Transpose
    df_result_clc = df_result_clc.T

    # Fill first column with blanks
    df_result_clc[0] = ''

    # Write xlsx file
    transpose_file = f"{csv_result_file[:len(csv_result_file) - 4]}_transpose.xlsx"
    with pd.ExcelWriter(transpose_file, engine='xlsxwriter') as writer:
        df_result_clc.to_excel(writer, sheet_name="Results", na_rep='', index=False, startrow=0, header=False)

    return transpose_file


def define_first_lines_hwascii(df_result_hwascii_crit_first_line):
    # Convert new line of df_result_hwascii_crit_first_line to list then to string
    result_type = df_result_hwascii_crit_first_line.values.flatten().tolist()
    result_type.pop(0)
    result_type = ','.join(result_type)

    cwd = os.getcwd()
    subcase = '$SUBCASE = 1 ' + cwd
    result_type = '$RESULT_TYPE = ' + result_type
    first_lines = ['ALTAIR ASCII FILE', '$BINDING = ELEMENT', '$COLUMN_INFO = ENTITY_ID', subcase, result_type,
                   '$DELIMITER = ,']
    first_lines = '\n'.join(first_lines)
    return first_lines


def prepend_file(file, first_lines):
    with open(file, 'r+') as f:
        content = f.read()
        f.seek(0)
        f.write(first_lines + '\n' + content)


def create_hwascii(criteria, df_result, csv_result_file, hwascii_file_list):
    # Create dataframe for hwascii
    df_result_hwascii = df_result.copy()

    # Create df_result_hwascii_crit
    df_result_hwascii_crit = df_result_hwascii.copy()
    df_result_hwascii_crit = df_result_hwascii_crit.query(f"Criteria == '{criteria}'")

    # Create a dataframe with LC name row
    df_result_hwascii_lc = df_result_hwascii.iloc[1:2]

    # Concat dataframes df_result_hwascii_crit and df_result_hwascii_lc
    df_result_hwascii_crit = pd.concat([df_result_hwascii_lc, df_result_hwascii_crit], join='inner')

    # Remove the unwanted columns
    df_result_hwascii_crit.drop(['empty0', 'Component', 'empty9', 'empty10', 'FE', 'Criteria', 'emptyCLC'], axis=1,
                                inplace=True)

    # Get first line of df_result_hwascii_crit
    df_result_hwascii_crit_first_line = df_result_hwascii_crit.loc[1, :]

    # Remove first line of df_result_hwascii_crit
    df_result_hwascii_crit = df_result_hwascii_crit.iloc[1:, :]

    # Append hwascii_file_list
    hwascii_file = f"{csv_result_file[:len(csv_result_file) - 4]}_{criteria}.hwascii"
    hwascii_file_list.append(hwascii_file)

    # Write hwascii file
    df_result_hwascii_crit.to_csv(hwascii_file, header=False, index=False)

    # Define new first lines of hwascii_file
    first_lines = define_first_lines_hwascii(df_result_hwascii_crit_first_line)

    # Add new first lines to hwascii_file
    prepend_file(hwascii_file, first_lines)

    return hwascii_file_list


def create_directory(folder):
    try:
        Path(Path(Path(), f'{folder}')).mkdir(parents=False, exist_ok=False)
        print(f"{folder} directory has been created...")

    except FileExistsError:
        print(f"Directory {folder} already exists")
        pass


def move_files(file_name, folder):
    shutil.move(file_name, Path.joinpath(Path(), folder, file_name))


def postprocess():
    # Define input
    lc_file = 'CWB_Internal_Frames_ULC_CLC_test2LC.xlsx'
    csv_result_file = '1_test_ACS_rod_ROD.csv'

    # Get load cases
    nb_ulc, list_clc_id, df_lc, list_lc = get_lc(lc_file)

    # Define criteria_list_to_keep
    criteria_list_to_keep = ['N', 'Stress']

    # Create synthesis
    df_result, criteria_list, synthesis_file = create_synthesis(csv_result_file, nb_ulc, list_clc_id, df_lc, list_lc,
                                                                criteria_list_to_keep)

    # Create transpose
    transpose_file = create_transpose(df_result, nb_ulc, csv_result_file)

    # Create HWascii files
    hwascii_file_list = []
    for criteria in criteria_list_to_keep:
        hwascii_file_list = create_hwascii(criteria, df_result, csv_result_file, hwascii_file_list)

    # Create folders
    for folder in ['SYNTHESES', 'TRANSPOSES', 'HWASCIIS']:
        create_directory(folder)

    # Move files
    move_files(synthesis_file, 'SYNTHESES')
    move_files(transpose_file, 'TRANSPOSES')
    for file in hwascii_file_list:
        move_files(file, 'HWASCIIS')

    print("end of post-processing")


def main():
    """
    Main instructions to run
    Call function: postprocess
    """
    postprocess()


if __name__ == '__main__':
    main()
