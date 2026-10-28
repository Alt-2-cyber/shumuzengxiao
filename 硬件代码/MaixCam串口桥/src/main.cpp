#include <Arduino.h>

HardwareSerial maixConsole(1);

void setup() {
  // Keep the environment relays inactive while this board is a console bridge.
  for (uint8_t pin : {14, 15, 16}) {
    digitalWrite(pin, HIGH);
    pinMode(pin, OUTPUT);
  }
  digitalWrite(21, LOW);
  pinMode(21, OUTPUT);
  Serial.begin(115200);
  maixConsole.begin(115200, SERIAL_8N1, 18, 17);
  delay(800);
  Serial.println("MAIX_UART_BRIDGE_READY rx=18 tx=17 baud=115200");
}

void loop() {
  uint8_t bytes[256];
  size_t available = maixConsole.available();
  if (available) {
    size_t count = maixConsole.readBytes(bytes, min(available, sizeof(bytes)));
    Serial.write(bytes, count);
  }
  available = Serial.available();
  if (available) {
    size_t count = Serial.readBytes(bytes, min(available, sizeof(bytes)));
    maixConsole.write(bytes, count);
  }
  delay(1);
}
