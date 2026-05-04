import math


def calculate_sinclair_coefficient(bodyweight_kg, gender='M'):
    if gender == 'M':
        a = 0.751945030
        b = 175.508
    else:
        a = 0.783497476
        b = 153.655

    if bodyweight_kg <= b:
        return 10 ** (a * (math.log10(bodyweight_kg / b)) ** 2)
    return 1.0


def calculate_sinclair_total(total_kg, bodyweight_kg, gender='M'):
    coefficient = calculate_sinclair_coefficient(bodyweight_kg, gender)
    return total_kg * coefficient

