#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:  2018/9/17 15:40
# @Author:  jessetjiang


TRAIN_FILE = 'data/train.csv'
TEST_FILE = 'data/test.csv'


SUB_DIR = 'output'

NUM_SPLITS = 3
RANDOM_SEED = 2018

# ALL_COLS = [
#     "label", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10",
#     "N11", "N12", "N13", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
#     "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19", "C20",
#     "C21", "C22", "C23", "C24", "C25", "C26"
# ]
#
# CATEGORY_COLS = [
#     "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10",
#     "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19",
#     "C20", "C21", "C22", "C23", "C24", "C25", "C26"
# ]
#
# NUMBERIC_COLS = [
#     "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10",
#     "N11", "N12", "N13"
# ]
#
# IGNORE_COLS = [
#     "label"
# ]
CATEGORICAL_COLS = [
    'ps_ind_02_cat', 'ps_ind_04_cat', 'ps_ind_05_cat',
    'ps_car_01_cat', 'ps_car_02_cat', 'ps_car_03_cat',
    'ps_car_04_cat', 'ps_car_05_cat', 'ps_car_06_cat',
    'ps_car_07_cat', 'ps_car_08_cat', 'ps_car_09_cat',
    'ps_car_10_cat', 'ps_car_11_cat',
]

NUMERIC_COLS = [
    "ps_reg_01", "ps_reg_02", "ps_reg_03",
    "ps_car_12", "ps_car_13", "ps_car_14", "ps_car_15",

    # feature engineering
    #"missing_feat", "ps_car_13_x_ps_reg_03",
]

IGNORE_COLS = [
    "id", "target",
    "ps_calc_01", "ps_calc_02", "ps_calc_03", "ps_calc_04",
    "ps_calc_05", "ps_calc_06", "ps_calc_07", "ps_calc_08",
    "ps_calc_09", "ps_calc_10", "ps_calc_11", "ps_calc_12",
    "ps_calc_13", "ps_calc_14",
    "ps_calc_15_bin", "ps_calc_16_bin", "ps_calc_17_bin",
    "ps_calc_18_bin", "ps_calc_19_bin", "ps_calc_20_bin"
]