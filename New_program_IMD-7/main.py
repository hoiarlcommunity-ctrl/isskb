import serial
import serial.tools.list_ports
import struct
import time
import csv
import json
import os
import winsound
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
from threading import Thread
import requests

class IMD07_App:
    def __init__(self, root):
        self.root = root
        self.root.title("Монитор ИМД-07 (Версия 2.5 - Финал)")
        self.root.geometry("600x730")
        self.root.configure(bg='#1e272e')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- СОСТОЯНИЯ ---
        self.port_is_open = False
        self.is_reading = False
        self.ser = None
        
        self.sound_enabled = True
        self.is_alarming = False
        
        # Тайминги и лимиты
        self.last_packet_time = time.time()
        self.no_signal_logged = False
        self.last_log_time = 0
        self.log_count = 0  
        
        # --- ПОРОГИ ПО УМОЛЧАНИЮ ---
        self.default_thresholds = {
            "pult_dr": 0.500,    # Пульт МЭД (мкЗв/ч)
            "pult_ed": 5.0,      # Пульт ЭД (мЗв)
            "vbd_dr": 0.500,     # ВБД МЭД (мкЗв/ч)
            "vbd_beta": 0.5,     # ВБД Бета (1/с*см2)
            "vbd_alpha": 0.03,   # ВБД Альфа (1/с*см2)
            # --- НОВЫЕ СЕТЕВЫЕ НАСТРОЙКИ ---
            "server_url": "http://127.0.0.1:8001/api/external/devices", # УКАЖИ IP СЕРВЕРА SENTINEL
            "device_name": "ИМД-07 (Вход)", # Уникальное имя этого прибора
            "send_interval": 5,  # Отправлять данные каждые 5 секунд
            "api_token": "",  # если на сервере задан SENTINEL_EXTERNAL_TOKEN — вписать сюда тот же токен
            "lat": 55.7558,  # <-- Широта (например, Москва)
            "lon": 37.6173   # <-- Долгота
        }
        self.thresholds = self.load_settings()
        self.last_send_time = 0  # Для таймера отправки

        # --- ВЕРХНЯЯ ПАНЕЛЬ (УПРАВЛЕНИЕ) ---
        frame_top = tk.Frame(root, bg='#1e272e')
        frame_top.pack(pady=10, fill=tk.X, padx=15)
        
        tk.Label(frame_top, text="Порт:", font=("Arial", 11), bg='#1e272e', fg='white').grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(frame_top, font=("Arial", 11), width=8)
        self.port_combo.grid(row=0, column=1, padx=5)
        tk.Button(frame_top, text="↻", command=self.update_ports, bg='#4bcffa').grid(row=0, column=2, padx=5)
        
        self.btn_start = tk.Button(frame_top, text="ПУСК", command=self.toggle, font=("Arial", 11, "bold"), bg='#05c46b', fg='white', width=10)
        self.btn_start.grid(row=0, column=3, padx=15)

        self.btn_sound = tk.Button(frame_top, text="ЗВУК: ВКЛ", command=self.toggle_sound, font=("Arial", 10, "bold"), bg='#3498db', fg='white')
        self.btn_sound.grid(row=0, column=4, padx=5)
        
        tk.Button(frame_top, text="ПОРОГИ", command=self.open_settings, font=("Arial", 10, "bold"), bg='#f39c12', fg='white').grid(row=0, column=5, padx=5)

        self.update_ports()

        # --- ПАНЕЛЬ ТРЕВОГИ ---
        self.frame_alarm = tk.Frame(root, bg='#ff3f34')
        self.lbl_alarm_text = tk.Label(self.frame_alarm, text="ВНИМАНИЕ! ПРЕВЫШЕНИЕ ПОРОГА!", font=("Arial", 14, "bold"), bg='#ff3f34', fg='white')
        self.lbl_alarm_text.pack(side=tk.LEFT, padx=20, pady=5)
        self.btn_reset_alarm = tk.Button(self.frame_alarm, text="СБРОС ТРЕВОГИ", command=self.reset_alarm, font=("Arial", 10, "bold"), bg='white', fg='#ff3f34')
        self.btn_reset_alarm.pack(side=tk.RIGHT, padx=20, pady=5)

        # --- ПАНЕЛЬ ДАННЫХ ---
        self.frame_data = tk.Frame(root, bg='#2f3640', bd=2, relief=tk.FLAT)
        self.frame_data.pack(pady=10, padx=15, fill=tk.BOTH)

        tk.Label(self.frame_data, text="Мощность дозы:", font=("Arial", 14), bg='#2f3640', fg='#d2dae2').pack(pady=(15,0))
        self.val_dose_rate = tk.StringVar(value="---")
        self.lbl_dose_rate = tk.Label(self.frame_data, textvariable=self.val_dose_rate, font=("Arial", 24, "bold"), bg='#2f3640', fg='#ffdd59')
        self.lbl_dose_rate.pack()

        tk.Label(self.frame_data, text="Погрешность:", font=("Arial", 12), bg='#2f3640', fg='#d2dae2').pack(pady=(10,0))
        self.val_error = tk.StringVar(value="--- %")
        tk.Label(self.frame_data, textvariable=self.val_error, font=("Arial", 16, "bold"), bg='#2f3640', fg='#0fbcf9').pack()

        tk.Label(self.frame_data, text="Накопленная доза:", font=("Arial", 12), bg='#2f3640', fg='#d2dae2').pack(pady=(10,0))
        self.val_accum = tk.StringVar(value="---")
        self.lbl_accum = tk.Label(self.frame_data, textvariable=self.val_accum, font=("Arial", 18, "bold"), bg='#2f3640', fg='#05c46b')
        self.lbl_accum.pack()

        self.val_time = tk.StringVar(value="Время: --:--:--")
        tk.Label(self.frame_data, textvariable=self.val_time, font=("Arial", 12), bg='#2f3640', fg='#808e9b').pack(pady=10)

        # --- ПАНЕЛЬ СТАТУСА ПРИБОРА ---
        frame_status = tk.Frame(root, bg='#1e272e')
        frame_status.pack(pady=5, fill=tk.X, padx=20)

        tk.Label(frame_status, text="Прибор:", font=("Arial", 11), bg='#1e272e', fg='white').pack(side=tk.LEFT, padx=(0, 5))
        self.canvas_health = tk.Canvas(frame_status, width=16, height=16, bg='#1e272e', highlightthickness=0)
        self.canvas_health.pack(side=tk.LEFT, padx=5)
        self.health_circle = self.canvas_health.create_oval(2, 2, 14, 14, fill='#7f8c8d') 
        
        self.lbl_health_status = tk.Label(frame_status, text="отключен", font=("Arial", 11, "bold"), bg='#1e272e', fg='#7f8c8d')
        self.lbl_health_status.pack(side=tk.LEFT, padx=5)

        self.lbl_power = tk.Label(frame_status, text="Питание: ---", font=("Arial", 11, "bold"), bg='#1e272e', fg='#bdc3c7')
        self.lbl_power.pack(side=tk.RIGHT, padx=10)

        # --- ОКНО СИСТЕМНОГО ЛОГА ---
        tk.Label(root, text="Системный лог:", font=("Arial", 10), bg='#1e272e', fg='#bdc3c7').pack(anchor="w", padx=20, pady=(5, 0))
        self.log_text = tk.Text(root, height=6, bg='#2f3640', fg='#d2dae2', font=("Courier New", 9), state=tk.DISABLED)
        self.log_text.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        self.log_label = tk.Label(root, text="Готов к работе. Выберите порт.", font=("Arial", 10), bg='#1e272e', fg='#bdc3c7')
        self.log_label.pack(side="bottom", pady=5)

        self.root.after(1000, self.check_signal_timeout)

    def log(self, message, level="INFO"):
        full_msg = f"[{time.strftime('%H:%M:%S')}] [{level}] {message}"
        print(full_msg)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, full_msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def send_to_server(self, payload):
        url = self.thresholds.get("server_url", "")
        if not url:
            return
        try:
            headers = {}
            api_token = str(self.thresholds.get("api_token", "")).strip()
            if api_token:
                headers["X-API-Key"] = api_token

            response = requests.post(url, json=[payload], headers=headers, timeout=10)
            if response.status_code not in (200, 201):
                self.log(f"Ошибка сервера: HTTP {response.status_code} | Ответ: {response.text}", "WARN")
            else:
                self.log(f"Данные отправлены в Sentinel: {response.status_code}", "NET")
        except Exception as e:
            self.log(f"Сетевая ошибка отправки: {e}", "ERROR")

    # --- БЛОК НАСТРОЕК (ПОРОГИ) ---
    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Не сбрасываем старые настройки, если в программе появились новые поля
                        merged = self.default_thresholds.copy()
                        merged.update(data)
                        return merged
        except Exception as e:
            print(f"Ошибка чтения settings.json: {e}")
        return self.default_thresholds.copy()

    def save_settings(self, new_thresholds):
        self.thresholds = new_thresholds
        try:
            with open("settings.json", "w") as f: json.dump(self.thresholds, f)
        except: pass

    def open_settings(self):
        win = Toplevel(self.root)
        win.title("Настройки порогов")
        win.geometry("450x300")
        win.configure(bg='#34495e')
        
        entries = {}
        labels = [
            ("Пульт МЭД (мкЗв/ч):", "pult_dr"),
            ("Пульт ЭД (мЗв):", "pult_ed"),
            ("ВБД МЭД (мкЗв/ч):", "vbd_dr"),
            ("ВБД Бета (1/с*см2):", "vbd_beta"),
            ("ВБД Альфа (1/с*см2):", "vbd_alpha")
        ]
        
        # Размещаем поля ввода
        for i, (text, key) in enumerate(labels):
            tk.Label(win, text=text, font=("Arial", 11), bg='#34495e', fg='white').grid(row=i, column=0, padx=15, pady=10, sticky="w")
            ent = tk.Entry(win, font=("Arial", 11), width=10)
            ent.insert(0, str(self.thresholds[key]))
            ent.grid(row=i, column=1, padx=15, pady=10)
            entries[key] = ent

        def save_and_close():
            try:
                new_t = {k: float(e.get()) for k, e in entries.items()}
                self.save_settings(new_t)
                win.destroy()
                messagebox.showinfo("Сохранено", "Пороги успешно обновлены!")
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректные числа (используйте точку).")

        def set_defaults():
            """Сброс всех полей до заводских значений"""
            for key, ent in entries.items():
                ent.delete(0, tk.END)
                ent.insert(0, str(self.default_thresholds[key]))

        # --- Кнопки "По умолчанию" и "Сохранить" ---
        frame_btns = tk.Frame(win, bg='#34495e')
        frame_btns.grid(row=5, column=0, columnspan=2, pady=15)

        tk.Button(frame_btns, text="По умолчанию", command=set_defaults, font=("Arial", 11, "bold"), bg='#95a5a6', fg='white', width=14).pack(side=tk.LEFT, padx=10)
        tk.Button(frame_btns, text="Сохранить", command=save_and_close, font=("Arial", 11, "bold"), bg='#2ecc71', fg='white', width=14).pack(side=tk.LEFT, padx=10)

    # --- БЛОК ТРЕВОГИ ---
    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        if self.sound_enabled:
            self.btn_sound.config(text="ЗВУК: ВКЛ", bg='#3498db')
        else:
            self.btn_sound.config(text="ЗВУК: ВЫКЛ", bg='#7f8c8d')
            winsound.PlaySound(None, winsound.SND_PURGE)

    def trigger_alarm(self, reason):
        if not self.is_alarming:
            self.is_alarming = True
            self.frame_alarm.pack(fill=tk.X, before=self.frame_data)
            self.lbl_alarm_text.config(text=f"ТРЕВОГА! {reason}")
            self.frame_data.config(bg='#c0392b')
            self.log(f"Сработала тревога: {reason}", "ALARM")
            
            if self.sound_enabled:
                if os.path.exists("ahoooga.wav"):
                    winsound.PlaySound("ahoooga.wav", winsound.SND_ASYNC | winsound.SND_LOOP)
                else:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    def reset_alarm(self):
        if self.is_alarming:
            self.is_alarming = False
            self.frame_alarm.pack_forget()
            self.frame_data.config(bg='#2f3640')
            winsound.PlaySound(None, winsound.SND_PURGE)

    def check_thresholds(self, pult_base_dr, pult_base_ed, ext_val=0, ext_type="gamma"):
        flag_pult_dr = "-"
        flag_pult_ed = "-"
        flag_vbd = "-"

        try:
            # 1. Проверяем пульт МЭД
            if pult_base_dr > (self.thresholds["pult_dr"] * 1e-6):
                self.trigger_alarm("Превышен порог МЭД (Пульт)!")
                flag_pult_dr = "превышен"
            
            # 2. Проверяем пульт ЭД
            if pult_base_ed > (self.thresholds["pult_ed"] * 1e-3):
                self.trigger_alarm("Превышена накопленная доза!")
                flag_pult_ed = "превышен"

            # 3. Проверяем внешний блок
            if ext_val > 0:
                if ext_type == "gamma" and ext_val > (self.thresholds["vbd_dr"] * 1e-6):
                    self.trigger_alarm("Превышен порог МЭД (ВБД)!")
                    flag_vbd = "превышен"
                elif ext_type == "beta" and ext_val > self.thresholds["vbd_beta"]:
                    self.trigger_alarm("Превышен порог Бета-излучения!")
                    flag_vbd = "превышен"
                elif ext_type == "alpha" and ext_val > self.thresholds["vbd_alpha"]:
                    self.trigger_alarm("Превышен порог Альфа-излучения!")
                    flag_vbd = "превышен"
        except Exception as e:
            self.log(f"Ошибка проверки порогов: {e}", "ERROR")

        return flag_pult_dr, flag_pult_ed, flag_vbd

    # --- ТАЙМАУТ СВЯЗИ ---
    def check_signal_timeout(self):
        if self.is_reading:
            if time.time() - self.last_packet_time > 8.0: 
                self.set_no_signal_state()
        self.root.after(1000, self.check_signal_timeout)

    def set_no_signal_state(self):
        self.val_dose_rate.set("НЕТ СВЯЗИ")
        self.val_error.set("--- %")
        self.val_accum.set("---")
        self.val_time.set("Время: --:--:--")
        self.canvas_health.itemconfig(self.health_circle, fill='#7f8c8d')
        self.lbl_health_status.config(text="нет связи", fg='#7f8c8d')
        self.lbl_power.config(text="Питание: ---", fg='#bdc3c7')
        self.reset_alarm()
        
        if not self.no_signal_logged:
            self.log("Потеря связи с прибором!", "WARN")
            self.no_signal_logged = True
            
            # --- НОВЫЙ БЛОК: Отправка статуса Offline ---
            payload = {
                "name": self.thresholds.get("device_name", "ИМД-07"),
                "online": False,
                "status": "offline"
            }
            Thread(target=self.send_to_server, args=(payload,), daemon=True).start()


    # --- БЛОК ЧТЕНИЯ ДАННЫХ ---
    def update_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combo['values'] = port_list
        if port_list: self.port_combo.current(0)
        else: self.port_combo.set("Нет портов")

    def check_crc(self, data):
        if len(data) < 2: return False
        crc_l, crc_h = 0xFF, 0xFF
        for i in range(len(data) - 2):
            crc_l ^= data[i]
            for _ in range(8):
                l_low = crc_l & 1
                h_low = crc_h & 1
                crc_h = (crc_h >> 1) & 0xFF
                crc_l = (crc_l >> 1) & 0xFF
                crc_l = (crc_l | (h_low << 7)) & 0xFF 
                if l_low == 1:
                    crc_l ^= 1
                    crc_h ^= 160
        return data[-2] == crc_l and data[-1] == crc_h

    def decode_val(self, h, m, l, d):
        try:
            mark = h & 128
            e_h = (h & 127) + 64
            e_d = (l & 1) << 7
            e_l = (l >> 1) + ((m & 1) << 7)
            e_m = (m >> 1) + ((e_h & 1) << 7)
            e_h = (e_h >> 1) + mark
            raw_float = struct.unpack('<f', bytes([e_d, e_l, e_m, e_h]))[0]
            
            mult_idx = (d & 48) >> 4
            unit_idx = d & 15
            units = {0: "", 1: "%", 2: "Зв", 3: "Зв/ч", 4: "1/(с*см2)", 5: "1/(мин*см2)"}
            unit = units.get(unit_idx, "?")

            base_val = raw_float
            if mult_idx == 1: 
                raw_float *= 1000.0
                unit = "м" + unit
            elif mult_idx == 2: 
                raw_float *= 1000000.0
                unit = "мк" + unit
                
            return round(raw_float, 4), unit, base_val
        except Exception:
            return 0.0, "ошибка", 0.0

    def process_packet(self, packet, mode_name):
        try:
            self.last_packet_time = time.time()
            self.no_signal_logged = False
            is_32 = (len(packet) == 32)
            
            dr_h, dr_m, dr_l, dr_d = packet[22:26] if is_32 else packet[3:7]
            dr_val, dr_unit, pult_base_dr = self.decode_val(dr_h, dr_m, dr_l, dr_d)
            
            err_val, _, _ = self.decode_val(packet[7], packet[8], packet[9], packet[10])
            acc_val, acc_unit, pult_base_ed = self.decode_val(packet[14], packet[15], packet[16], packet[17])
            time_str = f"{packet[18]:02x}:{packet[19]:02x}:{packet[20]:02x}"

            ext_base_val = 0
            ext_type = "gamma"
            ext_val, ext_unit = 0.0, ""

            if is_32:
                ext_val, ext_unit, ext_base_val = self.decode_val(packet[3], packet[4], packet[5], packet[6])
                vbd_byte = packet[11]
                if (vbd_byte & 8): ext_type = "alpha"
                elif (vbd_byte & 4): ext_type = "beta"
                
                self.val_dose_rate.set(f"ВБД: {ext_val} {ext_unit}\nПульт: {dr_val} {dr_unit}")
            else:
                self.val_dose_rate.set(f"{dr_val} {dr_unit}")

            self.val_error.set(f"± {err_val:.1f} %")
            self.val_accum.set(f"{acc_val} {acc_unit}")
            self.val_time.set(f"Время: {time_str}")

            err_code = packet[10]
            if err_code == 0:
                self.canvas_health.itemconfig(self.health_circle, fill='#2ecc71') 
                self.lbl_health_status.config(text="исправен", fg='#2ecc71')
            else:
                self.canvas_health.itemconfig(self.health_circle, fill='#e74c3c') 
                self.lbl_health_status.config(text=f"ошибка {err_code:02X}", fg='#e74c3c')

            status_byte = packet[11]
            ext_power = (status_byte & 64) >> 6     
            low_battery = (status_byte & 128) >> 7   

            if ext_power == 1:
                self.lbl_power.config(text="Питание: Сеть 🔌", fg='#2ecc71')
            else:
                if low_battery == 1:
                    self.lbl_power.config(text="Батарея: Разряжена ⚠️", fg='#e74c3c')
                else:
                    self.lbl_power.config(text="Батарея: Норма 🔋", fg='#3498db')

            # Получаем статусы порогов
            f_dr, f_ed, f_vbd = self.check_thresholds(pult_base_dr, pult_base_ed, ext_base_val, ext_type)

            # Сохранение со всеми флагами
            self.save_to_csv(mode_name, dr_val, dr_unit, err_val, acc_val, acc_unit, time_str, ext_val, ext_unit, f_dr, f_ed, f_vbd)

            # --- НОВЫЙ БЛОК: ОТПРАВКА НА СЕРВЕР SENTINEL ---
            current_time = time.time()
            send_interval = self.thresholds.get("send_interval", 5)
            
            if current_time - self.last_send_time > send_interval:
                self.last_send_time = current_time
                
                # Определяем статус (если тревога - шлем alarm, иначе active)
                status_mode = "active"
                if self.is_alarming or f_dr != "-" or f_ed != "-" or f_vbd != "-":
                    status_mode = "alarm"

                # Формируем JSON
                payload = {
                    "name": self.thresholds.get("device_name", "ИМД-07 (Тест)"),
                    "online": True,
                    "status": status_mode,
                    "device_type": "Дозиметр ИМД-07",
                    "battery_level": 100 if ext_power == 1 else (10 if low_battery == 1 else 80),
                    "dose_rate": f"{dr_val} {dr_unit}",
                    "error_percent": f"± {err_val:.1f} %",
                    "accumulated_dose": f"{acc_val} {acc_unit}",
                    "vbd_data": f"{ext_val} {ext_unit}" if ext_val > 0 else "—",
                    "lat": self.thresholds.get("lat", 55.7558), # <-- ДОБАВИЛИ
                    "lon": self.thresholds.get("lon", 37.6173)  # <-- ДОБАВИЛИ
                }
                Thread(target=self.send_to_server, args=(payload,), daemon=True).start()

        except Exception as e:
            self.log(f"Ошибка парсинга пакета: {e}", "ERROR")

    def save_to_csv(self, mode, dr_val, dr_unit, err_val, acc_val, acc_unit, time_str, ext_val, ext_unit, flag_dr, flag_ed, flag_vbd):
        current_time = time.time()
        if current_time - self.last_log_time < 30.0:
            return
        
        self.last_log_time = current_time
        
        try:
            file_name = "imd07_data.csv"
            file_exists = os.path.exists(file_name)
            
            with open(file_name, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Mode", "Порог МЭД пульта", "DoseRate_Pult", "Unit_Pult", "Error_%", "Порог ЭД пульта", "AccumulatedDose", "AccumUnit", "TimeStr", "Порог ВБД", "DoseRate_VBD", "Unit_VBD"])
                writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), mode, flag_dr, dr_val, dr_unit, err_val, flag_ed, acc_val, acc_unit, time_str, flag_vbd, ext_val, ext_unit])
            
            self.log(f"Запись в файл истории (раз в 30с).")
            
            self.log_count += 1
            if self.log_count >= 100:
                self.log_count = 0
                self.rotate_log(file_name, 1000000)
        except Exception as e:
            self.log(f"Ошибка сохранения истории: {e}", "ERROR")

    def rotate_log(self, file_name, max_lines):
        if not os.path.exists(file_name): return
        try:
            with open(file_name, "r") as f:
                lines = f.readlines()
            
            if len(lines) > max_lines:
                header = lines[0] if lines else "Timestamp,Mode,Порог МЭД пульта,DoseRate_Pult,Unit_Pult,Error_%,Порог ЭД пульта,AccumulatedDose,AccumUnit,TimeStr,Порог ВБД,DoseRate_VBD,Unit_VBD\n"
                kept_lines = lines[-(max_lines - 1):]
                
                with open(file_name, "w") as f:
                    f.write(header)
                    f.writelines(kept_lines)
                self.log(f"Автоочистка: удалены старые строки логов.", "SYSTEM")
        except: pass

    def handle_crash(self, msg):
        self.port_is_open = False
        self.is_reading = False
        try: self.ser.close()
        except: pass
        self.btn_start.config(text="ПУСК", bg="#05c46b")
        self.log_label.config(text=msg, fg="#ff3f34")
        self.log(msg, "CRASH")
        self.reset_alarm()

    def read_loop(self):
        buffer = bytearray()
        while self.port_is_open:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    if not self.is_reading:
                        buffer.clear()
                        continue
                    buffer.extend(data)
                
                if not self.is_reading:
                    time.sleep(0.1)
                    continue

                while len(buffer) > 0:
                    if buffer[0] == 0x05:
                        if len(buffer) >= 7: buffer = buffer[7:]
                        else: break
                    elif buffer[0] == 0x01 and len(buffer) >= 3:
                        if buffer[1] == 0x0C and buffer[2] == 0x13: 
                            if len(buffer) >= 24:
                                if self.check_crc(buffer[:24]):
                                    self.process_packet(buffer[:24], "РЕЖИМ 1 (ПУЛЬТ)")
                                    buffer = buffer[24:]
                                    continue
                                else: buffer.pop(0)
                            else: break
                        elif buffer[1] == 0x0C and buffer[2] == 0x1B:
                            if len(buffer) >= 32:
                                if self.check_crc(buffer[:32]):
                                    self.process_packet(buffer[:32], "РЕЖИМ 2 (ВБД)")
                                    buffer = buffer[32:]
                                    continue
                                else: buffer.pop(0)
                            else: break
                        else: buffer.pop(0)
                    else: buffer.pop(0)
                    
            except serial.SerialException as e:
                self.root.after(0, lambda: self.handle_crash(f"Скачок напряжения! Вытащите кабель. Ошибка: {e}"))
                break
            except Exception: pass
            
            time.sleep(0.05)

    def toggle(self):
        if not self.port_is_open:
            port = self.port_combo.get()
            if not port or "Нет" in port: return
            try:
                self.ser = serial.Serial()
                self.ser.port = port
                self.ser.baudrate = 9600
                self.ser.stopbits = serial.STOPBITS_TWO
                self.ser.timeout = 0.5
                self.ser.dtr = False
                self.ser.rts = True
                self.ser.open()
                
                time.sleep(0.5)
                self.ser.reset_input_buffer()
                
                self.port_is_open = True
                self.is_reading = True
                self.last_packet_time = time.time() 
                
                self.btn_start.config(text="СТОП", bg="#ff3f34")
                self.log_label.config(text=f"Чтение порта {port}...", fg='#bdc3c7')
                
                Thread(target=self.read_loop, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Порт недоступен.\n\nДетали: {e}")
        else:
            if self.is_reading:
                self.is_reading = False
                self.btn_start.config(text="ПУСК", bg="#05c46b")
                self.set_no_signal_state() 
            else:
                self.is_reading = True
                self.btn_start.config(text="СТОП", bg="#ff3f34")
                self.last_packet_time = time.time()

    def on_closing(self):
        self.port_is_open = False
        self.reset_alarm()
        if self.ser and self.ser.is_open:
            try:
                self.ser.reset_input_buffer()
                self.ser.close()
            except: pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = IMD07_App(root)
    root.mainloop()