import os
from faker import Faker

def optim_workers():
    return max(1, os.cpu_count() - 1)

def fake_name():
    fake = Faker()
    fake_name = fake.name().split()[0]
    fake_pwd = fake.password(
        length=8, special_chars=False,
        digits=True, upper_case=True, lower_case=False
    )
    return fake_name + "_" + fake_pwd