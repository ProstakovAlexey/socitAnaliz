#!/usr/bin/python3
__author__ = 'Prostakov Alexey'
"""
Описание
**********************

Входные данные
**********************

Выходные данные
**********************

"""
import os, glob
import csv
from pymongo import MongoClient
import sys
import configparser
import logging
import subprocess
import datetime


logging.basicConfig(filename='graph.log', filemode='a', level=logging.DEBUG,
    format='Протокол: %(asctime)s %(levelname)s: %(message)s')
# определение для gnuplot
smev = r"""
set terminal  png size 600,400 font 'Verdana, 7'
set output "#DIR#/СМЭВ.png"
set title "СМЭВ #TITLE#"
set label "Отправлено запросов: #REQ#\nДано ответов:#RESP#" at graph 0.1, graph 0.9
set ylabel "Кол-во запросов(ответов) в час"
set xrange[0:24]
set xlabel "Часы"
set grid xtics ytics
set key top right
set xtic rotate by 90 scale 0 offset character 0,-2
plot '#DIR#/response.txt' u 1:2 ti "Ответы" w linespoints lw 2 pt 2,\
'#DIR#/request.txt' u 1:2 ti "Запросы" w linespoints lw 2 pt 4
"""
pgu = r"""
set terminal  png size 600,400 font 'Verdana, 7'
set output "#DIR#/ПГУ.png"
set title "Заявленния ПГУ #TITLE#"
set label "Принято заявлений: #REQ#\nДано ответов:#RESP#" at graph 0.1, graph 0.9
set ylabel "Кол-во заявлений(ответов) в час"
set xrange[0:24]
set xlabel "Часы"
set grid xtics ytics
set key top right
set xtic rotate by 90 scale 0 offset character 0,-2
plot '#DIR#/pgu.txt' u 1:2 ti "Заявления" w linespoints lw 2 pt 2,\
'#DIR#/status.txt' u 1:2 ti "Решения" w linespoints lw 2 pt 4
"""


def readConfig(file="config.ini"):
    '''
    :param file: имя файла конфигурации
    :return: список ИС для тестирования, словарь настроек к БД, кол-во ошибок
    '''
    err = 0
    ISList = list()
    BD = dict()
    if os.access(file, os.F_OK):
        # выполняется если найден конфигурационный файл
        config_str = open(file, encoding='utf-8', mode='r').read()
        # удалить признак кодировки
        config_str = config_str.replace(u'\ufeff', '')
        # чтение конфигурационного файла
        Config = configparser.ConfigParser()
        Config.read_string(config_str)
        sections = Config.sections()
        # читаем все секции
        for section in sections:
            i = Config[section]
            # это секция про ИС, их может быть несколько
            if section.count('IS'):
                IS = dict()
                IS['snd_name'] = i.get('name', fallback='СОЦИНФОРМТЕХ')
                IS['snd_code'] = i.get('mnemonic', fallback='SOCP01711')
                IS['oktmo'] = i.get('OKTMO', fallback='70000000')
                IS['url'] = i.get('URL', fallback='/socportal/')
                IS['adr'] = i.get('address', fallback='')
                IS['port'] = i.get('port', fallback='80')
                IS['servicecode'] = i.get('SERVICE_CODE', fallback='123456789')
                IS['SpravID'] = i.get('SpravID', fallback='1')
                IS['comment'] = i.get('comment', fallback='')
                IS['373'] = i.get('373', fallback='no')
                IS['409'] = i.get('409', fallback='no')
                IS['510'] = i.get('510', fallback='no')
                IS['PGU'] = i.get('PGU', fallback='no')
                IS['1003'] = i.get('1003', fallback='no')
                IS['1004'] = i.get('1004', fallback='no')
                IS['1005'] = i.get('1005', fallback='no')
                IS['1007'] = i.get('1007', fallback='no')
                IS['web'] = i.get('web', fallback='no')
                IS['protocol'] = i.get('protocol', fallback='no')
                ISList.append(IS)
            # это про подсоединение к БД
            elif section == 'BD':
                BD['adr'] = i.get('address', fallback='')
                BD['port'] = i.get('port', fallback='27017')
                BD['BD'] = i.get('dataBase', fallback='')
                BD['collection'] = i.get('collection', fallback='')
                BD['protocol'] = i.get('protocol', fallback='')
        # проверим заполнение секции о БД
        if len(BD.keys()) == 0:
            print('В конфигурационном файле отсутствует обязательная секция о БД.')
            err += 1
        else:
            for key in BD.keys():
                if BD[key] == '':
                    print("Параметр %s не должен быть пустой, заполните его в конфигурационном файле %s" % (key, file))
                    err += 1
        # проверим заполнение сведений об ИС
        if len(ISList) == 0:
            print('В конфигурационном файле отсутствует обязательная секция об ИС.')
            err += 1
        else:
            for IS in ISList:
                for key in IS.keys():
                    if IS[key] == '':
                        print("В секции сведение об ИС параметр %s не должен быть пустой, заполните его в конфигурационном файле %s" % (key, file))
                        err += 1
    # нет конфигурационного файла
    else:
        print("Ошибка! Не найден конфигурационный файл")
        err = 1
    return ISList, BD, err


def getDataFile(collection, get, Dir):
    """
    Извлекает данные из БД и сохраняет в файлы, чтобы gnuplot мог их прочитать
    Файл для сохранения:
    - запросы request.txt
    - ответы response.txt
    - заявления ПГУ pgu.txt
    - ответы на заявления ПГУ status.txt
    :param collection: объек с коллекцией
    :param get: запрос к БД
    :param Dir: папка для сохранения файлов
    :return: кол-во ошибок
    """
    res = 1
    date = get['date']
    logging.debug('Запущен поиск протоколов на дату %s' % date)
    result = collection.find(get)
    logging.debug('Строка поиска: %s' % get)
    if result:
        # получен результат
        f1 = open(Dir+'/'+'request.txt', 'w')
        f2 = open(Dir+'/'+'response.txt', 'w')
        f3 = open(Dir+'/'+'pgu.txt', 'w')
        f4 = open(Dir+'/'+'status.txt', 'w')
        for post in result:
            print('Ответ из БД: %s' % post)
            # ищем для запросов
            if post['request']:
                for i in post['request']:
                    print("%s\t%s" % (i[0], i[1]), file=f1)
            else:
                # добавим пустое значение, чтобы график не упал
                print("12\t0", file=f1)
            # ищем для ответов
            if post['response']:
                for i in post['response']:
                    print('%s\t%s' % (i[0], i[1]), file=f2)
            else:
                # добавим пустое значение, чтобы график не упал
                print("12\t0", file=f2)
            # ищем для заявлений
            if post['zaiv']:
                for i in post['zaiv']:
                    print('%s\t%s' % (i[0], i[1]), file=f3)
            else:
                # добавим пустое значение, чтобы график не упал
                print("12\t0", file=f3)
            # ищем для статусов
            if post['status']:
                for i in post['status']:
                    print('%s\t%s' % (i[0], i[1]), file=f4)
            else:
                # добавим пустое значение, чтобы график не упал
                print("12\t0", file=f4)
        f1.close()
        f2.close()
        f3.close()
        f4.close()
        logging.debug('За дату %s протокол получен' % date)
    else:
        # за эту дату нет протокола
        res = 0
        logging.debug('За дату %s нет протокола' % date)
    return(res)


def plotGraph(post, dirName, dateStr):
    """ Строит графики по времени"""
    # для СМЭВ запросов
    fs = open('gnuplot.tmp', 'w')
    sh = smev.replace("#DIR#", dirName)
    sh = sh.replace("#TITLE#", post['comment']+' '+dateStr)
    # надо подсчитать кол-во СМЭВ запросов
    with open(dirName+'/'+'request.txt') as csvfile:
        summ = 0
        for row in csv.reader(csvfile, delimiter='\t'):
            summ += int(row[1])
    sh = sh.replace("#REQ#", str(summ))
    # надо подсчитать кол-во ответов на СМЭВ запросы
    with open(dirName+'/'+'response.txt') as csvfile:
        summ = 0
        for row in csv.reader(csvfile, delimiter='\t'):
            summ += int(row[1])
    sh = sh.replace("#RESP#", str(summ))
    print(sh, file=fs)
    fs.close()
    err = subprocess.call(["gnuplot", 'gnuplot.tmp'])
    if err:
        logging.error("При вызове gnuplot возникла ошибка")
    else:
        logging.info("График %s построен успешно" % post['name'])
    # для ПГУ запросов
    fs = open('gnuplot.tmp', 'w')
    sh = pgu.replace("#DIR#", dirName)
    sh = sh.replace("#TITLE#", post['comment']+' '+dateStr)
    # надо подсчитать кол-во СМЭВ запросов
    with open(dirName+'/'+'pgu.txt') as csvfile:
        summ = 0
        for row in csv.reader(csvfile, delimiter='\t'):
            summ += int(row[1])
    sh = sh.replace("#REQ#", str(summ))
    # надо подсчитать кол-во ответов на СМЭВ запросы
    with open(dirName+'/'+'status.txt') as csvfile:
        summ = 0
        for row in csv.reader(csvfile, delimiter='\t'):
            summ += int(row[1])
    sh = sh.replace("#RESP#", str(summ))
    print(sh, file=fs)
    fs.close()
    err = subprocess.call(["gnuplot", 'gnuplot.tmp'])
    if err:
        logging.error("При вызове gnuplot возникла ошибка")
    else:
        logging.info("График %s построен успешно" % post['name'])


if __name__ == '__main__':
    # Выполняется если файл запускается как программа
    logging.info('Запуск программы')
    ISList, BD, err = readConfig('config.ini')
    if err > 0 or ISList is None or BD is None:
        logging.critical("При чтении конфигурационного файла произошли ошибки. Программа остановлена")
        exit(1)
    else:
        logging.info("Конфигурационный файл прочитан успешно.")

    # соединяемся с БД для записи протокола
    try:
        client = MongoClient(BD['adr'], int(BD['port']))
        db = client[BD['BD']]
        collection = db[BD['protocol']]
    except:
        logging.critical("Ошибка при соединении с БД. Программа остановлена")
        Type, Value, Trace = sys.exc_info()
        logging.critical("""Тип ошибки: %s
Текст: %s""" % (Type, Value))
        exit(2)
    logging.info('Успешное соединения с БД')
    # получаем дату за вчера, важно получить только дату, без времени
    date = datetime.datetime.today() - datetime.timedelta(days=1)
    date = datetime.datetime(date.year, date.month, date.day)
    logging.info('Ищем на дату %s' % date)
    # перебираем все ИС из конф. файла
    for IS in ISList:
        logging.info('Обрабатываем ИС: %s' % IS['snd_name'])
        # пишем в папку
        dirName = 'Графики/' + IS['comment']
        if IS['protocol'] == 'yes':
            get = {
                "name": "Протокол",
                "comment": IS['comment'],
                "date": date
            }
            # пробуем получить данные протокола в файлы
            if getDataFile(collection, get, dirName):
                # успешно получены, строим график
                logging.debug('Строим графики')
                plotGraph(get, dirName, date.strftime('%d.%m.%Y'))
    exit(0)
