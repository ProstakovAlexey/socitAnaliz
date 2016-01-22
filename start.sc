#!/bin/bash
python3 web-service_Graph.py
# удаляем временные файлы                                                    
rm gnuplot.tmp                                       
rm data.tmp 
python3 protocolAnalize.py
# копирование подготовленных файлов                                         
#rm -R html/fig/*                                  
cp -R Графики/* html/fig/
