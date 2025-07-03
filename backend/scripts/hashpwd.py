# -*- coding: utf-8 -*-
"""
Created on Thu May  8 13:34:41 2025

@author: sdeekollu
"""

import bcrypt

password = b"Hello123!"
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed)
