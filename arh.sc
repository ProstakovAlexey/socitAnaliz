#!/bin/bash
name=`date +'%Y-%m-%d'`
mkdir $name
cp html/*html $name
cp -R html/fig $name
cp -R html/css $name

# вывод результатов по протоколу
python3 protocolAnalize.py
