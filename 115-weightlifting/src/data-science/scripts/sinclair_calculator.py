"""
Sinclair Score Calculator for Olympic Weightlifting
Calculates the Sinclair coefficient and adjusted total based on bodyweight.
"""

import math


def calculate_sinclair_coefficient(bodyweight_kg, gender='M'):
    """
    Calculate the Sinclair coefficient for a given bodyweight.
    
    Args:
        bodyweight_kg: Bodyweight in kilograms
        gender: 'M' for male, 'F' for female
    
    Returns:
        Sinclair coefficient
    """
    if gender == 'M':
        a = 0.751945030
        b = 175.508
    else:  # Female
        a = 0.783497476
        b = 153.655
    
    if bodyweight_kg <= b:
        coefficient = 10 ** (a * (math.log10(bodyweight_kg / b)) ** 2)
    else:
        coefficient = 1.0
    
    return coefficient


def calculate_sinclair_total(total_kg, bodyweight_kg, gender='M'):
    """
    Calculate the Sinclair-adjusted total.
    
    Args:
        total_kg: Competition total in kilograms
        bodyweight_kg: Bodyweight in kilograms
        gender: 'M' for male, 'F' for female
    
    Returns:
        Sinclair-adjusted total
    """
    coefficient = calculate_sinclair_coefficient(bodyweight_kg, gender)
    return total_kg * coefficient

