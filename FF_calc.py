import pandas as pd
import ruptures as rpt
import numpy as np
import os
from tkinter import filedialog, Tk, messagebox, ttk, StringVar, Entry, END, Label

#ф-я для интерполяции GOR_&_WCT по новой накопленной нефти(прирастает единым шагом), необходима т.к. rpt работает с 1d array
def interpolated_data(df_, well_name):
    #расчет новой накопленной нефти
    data_for_trend = df_[df_['well_name']==well_name].sort_index().reset_index()#['2021-01':'2021-08']
    Num_val=len(data_for_trend['gor'])
    Well_CumOil=np.array(data_for_trend['oil_accum'][-1:])
    Av_Oil_Prod=Well_CumOil/Num_val
    data_for_trend['OilCumSum'] = pd.Series(list(range(1, Num_val+1))) * Av_Oil_Prod[0]
    #интерполяция GOR&WCT
    x=data_for_trend['oil_accum']
    x1=data_for_trend['OilCumSum']
    y_gor=data_for_trend['gor']
    y_wct=data_for_trend['wct']
    y_IntGOR=np.interp(x1,x,y_gor)
    y_IntWCT=np.interp(x1,x,y_wct)
    data_for_trend.insert(10,"Inter_gor",y_IntGOR)
    data_for_trend.insert(10,"Inter_wct",y_IntWCT)
    return {'data_for_trend':data_for_trend, 'Av_Oil_Prod':Av_Oil_Prod, 'Num_val':Num_val, 'Well_CumOil':Well_CumOil}



#чистка пиков GOR/WCT
def PicsCorrection(result_, data_for_trend_, column_):
    if len(result_)==1:
        Q1 = data_for_trend_[column_].quantile(0.25)
        Q3 = data_for_trend_[column_].quantile(0.75)
        IQR = Q3 - Q1
        data_for_trend_.loc[data_for_trend_[column_] <= Q1-1.5*IQR, column_] = np.NaN
        data_for_trend_.loc[data_for_trend_[column_] >= Q3+1.5*IQR, column_] = np.NaN
        data_for_trend_[column_].fillna(method="ffill",inplace=True)
        data_for_trend_[column_].fillna(method="bfill",inplace=True)

    else:
        Q1 = data_for_trend_[result_[-2]:][column_].quantile(0.25)
        Q3 = data_for_trend_[result_[-2]:][column_].quantile(0.75)
        IQR = Q3 - Q1
        data_for_trend_[result_[-2]:].loc[data_for_trend_[column_] <= Q1-1.5*IQR, column_] = np.NaN
        data_for_trend_[result_[-2]:].loc[data_for_trend_[column_] >= Q3+1.5*IQR, column_] = np.NaN
        data_for_trend_[result_[-2]:][column_].fillna(method="ffill",inplace=True)
        data_for_trend_[result_[-2]:][column_].fillna(method="bfill",inplace=True)
    data=data_for_trend_
    return data


#ф-я ruptures для определения интервала тренда, исправление пиков в данных, определение коэффициентов тренда (y=kx+b)
def RPT_(_data_for_trend, column, well_name):
    try:
        points = np.array(_data_for_trend[column])
        x_ = np.arange(len(points)+90)
        #RUPTURES PACKAGE
        #определение интервала тренда
        model="rbf"
        algo = rpt.Pelt(model=model).fit(points)
        result = algo.predict(pen=10)

        #исправление пиков в данных 
        _data_for_trend = PicsCorrection(result, _data_for_trend, column)
        #построение тренда
        if len(result)!=1:
            x = x_[result[-2]:-90]
            x_pr = x_[result[-2]:]
            y = _data_for_trend[result[-2]:][column]
        else:
            x = x_[:-90]
            x_pr = x_
            y = _data_for_trend[column]
        z= np.polyfit(x, y, 1)
        z = np.squeeze(z)

        return {'z':z, 'points':points, 'result':result, 'x_pr':x_pr, 'y':y, 'column':column, 'well':well_name}

    except: 
        pass



#определение ближайшего шага ранней даты, на случай, если в выбранную дату скважина не работала
def get_DateStep(data_for_trend_, date_):
    well_data = data_for_trend_.query('measure_date <= @date_')
    return well_data[-1:].index.values[0]



def prepare_data(direct_):
    df_ = pd.read_csv(direct_, 
                 #sep=';', 
                 encoding='cp1251', 
                 quotechar="\"",
                 parse_dates=[1],
                 ) #index_col=[1]
    #расчет дебитов
    df_.fillna(0, inplace=True)
    df_['oil_rate'] = df_.groupby('well_name')['oil_accum'].diff().fillna(df_['oil_accum'])
    df_['gas_rate'] = df_.groupby('well_name')['gaz_accum'].diff().fillna(df_['gaz_accum'])
    df_['water_rate'] = df_.groupby('well_name')['water_accum'].diff().fillna(df_['water_accum'])
    df_['gor'] = df_['gas_rate'] / df_['oil_rate']
    df_['wct'] = df_['water_rate']  / (df_['water_rate'] + df_['oil_rate']) * 100
    #чистка данных
    df_['days'] = df_.groupby('well_name')['measure_date'].diff()
    df_.dropna(inplace=True)
    #df_.set_index('measure_date', inplace=True)
    df_.drop(df_[df_['oil_accum']==0].index, inplace=True)
    df_.drop(df_[df_['gor']==0].index, inplace=True)
    df_.drop(df_[df_['gor']==np.inf].index, inplace=True)
    df_.drop(df_[df_['gor']>10000].index, inplace=True)
    return df_
 
  

def main_calc_body():
    global file_directory, date_entry, folder
    df = prepare_data(file_directory)
    date = date_entry.get()
    ExpDF = pd.DataFrame()
    #цикл по скважинам 
    for well in df['well_name'].unique(): #df['well_name'].unique()
        try:
            #print(well)
            #получение данных, интерполяция GOR/WCT
            interpolated_data_Results=interpolated_data(df, well)
            data_for_trend = interpolated_data_Results['data_for_trend']
            Av_Oil_Prod = interpolated_data_Results['Av_Oil_Prod'][0]
            

            #Создание папок для сохранения графиков
            newpath = r''+folder+'/GOR' 
            if not os.path.exists(newpath):
                os.makedirs(newpath)
                
            newpath = r''+folder+'/WCT' 
            if not os.path.exists(newpath):
                os.makedirs(newpath)
        

            #Ruptures_WCT
            RPTresultsWCT = RPT_(data_for_trend, 'Inter_wct', well)
            
            
            #Ruptures_GOR
            RPTresultsGOR = RPT_(data_for_trend, 'Inter_gor', well)
            
            
            #поиск шага по заданной пользователем дате
            try:
                DateStep=np.array(data_for_trend.query("measure_date == @date").index.values)[0]
            #если даты нет, берется более ранняя дата 
            except:
                DateStep=get_DateStep(data_for_trend, date)

            #расчет параметров для выгрузки фф в csv       
            kGOR=RPTresultsGOR['z'][0]
            bGOR=RPTresultsGOR['z'][1]
            kWCT=RPTresultsWCT['z'][0]
            bWCT=RPTresultsWCT['z'][1]
            GOR0=bGOR+DateStep*kGOR

            #ограничения по параметрам (GOR 50-inf,WCT 0-98)
            if GOR0<=50:
                GOR0=50
            GOR1=bGOR+(DateStep+90)*kGOR
            if GOR1<=50:
                GOR1=50
            WCT0=bWCT+DateStep*kWCT
            if WCT0<=0:
                WCT0=0
            if WCT0>=100:
                WCT0=98
            WCT1=bWCT+(DateStep+90)*kWCT
            if WCT1<=0:
                WCT1=0
            if WCT1>=100:
                WCT1=98
            dCumOil=90*Av_Oil_Prod
            #запись паарметров в df   
            ExpDF=ExpDF.append({'WELL':well,'0OCUM':0,'OilCum':dCumOil,'GOR0':GOR0,'GOR1':GOR1,'WCT0':WCT0,'WCT1':WCT1,'KGOR':kGOR,'bGOR':bGOR,'kWCT':kWCT,'bWCT':bWCT},ignore_index=True)

        except: 
            pass
    #экспорт в csv
    files_path_to_save = r''+folder+'/ExpDF.csv'
    check(ExpDF, files_path_to_save)

def info_success():
    info_success = messagebox.showinfo(title='Информация', message='Готово')


def info_error():
    info_error = messagebox.showinfo(title='Информация', message='Ошибка')
    
# Проверка существования файла после отработки скрипта и сохранение файла
def check(ExpDF_, files_path):
    if os.path.exists(files_path):
        answer = messagebox.askyesno(title="Внимание", message="Сsv файл уже существует в этой папке, перезаписать?")
        if answer:
            ExpDF_.to_csv(files_path, sep=';', line_terminator='\n')
            info_success()
        else:
            pass
    else:
        ExpDF_.to_csv(files_path, sep=';', line_terminator='\n')
        info_success()

#переменная для получения пути к файлу
def calc_ff():
    global folder, file_directory, date_entry
    file_directory = filedialog.askopenfilename(title="Выберите scv файл", filetypes=[('.csv', '.csv')])
    directory = file_directory
    if not file_directory:
        pass
    else:
        window.destroy
        pos=file_directory.rindex("/", 0,len(file_directory))
        folder=directory[0:pos]
        folder=r''+folder
        print (folder)
        print (file_directory)
        #print(prepare_data(file_directory))
        main_calc_body()
        print(date_entry.get())
        return folder        
            
            


title='Выберите CSV файл с посуточными накопленными показателями'
window = Tk()
window.title(title)
window.geometry('750x100')
window.configure(background='white')

inputdate = StringVar()
date_entry = Entry(textvariable=inputdate, width=50)
date_entry.insert(END, '2022-01-01')
date_entry.place(relx=.5, rely=.1, anchor="c")
#date_entry.configure(state=DISABLED)

Label(window, text="Скв и даты в двойных кавычках, разделитель запятая").place(x=420,y=37)

b2 = ttk.Button(window, text='Выбрать файл', command=calc_ff)
b2.pack(expand=1)
window.mainloop()



  