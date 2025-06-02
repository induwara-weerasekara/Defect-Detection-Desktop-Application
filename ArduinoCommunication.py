import serial
import time

class ArduinoCommunication:
    def __init__(self, port='COM3', baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.arduino = None

    def connect(self):
        try:
            self.arduino = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2)  # Allow time for Arduino to initialize
            print(f"Connected to Arduino on {self.port}.")
            return True
        except Exception as e:
            print(f"Error connecting to Arduino: {e}")
            return False

    def send_defect_status(self, status):
        try:
            if self.arduino and self.arduino.is_open:
                if status == "Defective":
                    print("Sending 'D' to Arduino for Defective")
                    self.arduino.write(b'D')  # Send 'D' for Defective (red bulb)
                elif status == "Intact":
                    print("Sending 'I' to Arduino for Intact")
                    self.arduino.write(b'I')  # Send 'I' for Intact (green bulb)
                print(f"Sent status to Arduino: {status}")
            else:
                print("Arduino is not connected.")
        except Exception as e:
            print(f"Error sending defect status: {e}")

    def close(self):
        try:
            if self.arduino and self.arduino.is_open:
                self.arduino.close()
                print("Arduino connection closed.")
        except Exception as e:
            print(f"Error closing Arduino connection: {e}")