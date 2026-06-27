/*
  ============================================================
  Projet  : AI Smart Environmental Monitoring Platform
  Carte   : ESP32 Wokwi
  Cloud   : ThingSpeak
  Capteurs:
    - DHT22    : température + humidité
    - LM35     : température analogique
    - LDR      : luminosité
    - PIR      : détection de mouvement
    - HC-SR04  : distance
  Actionneurs:
    - RGB LED
    - Buzzer
    - OLED I2C

  ThingSpeak Fields:
    field1 -> DHT22 Temperature
    field2 -> Humidity
    field3 -> LM35 Temperature
    field4 -> Luminosity %
    field5 -> Motion
    field6 -> Distance cm
    field7 -> Risk Score
    field8 -> Alert Code
  ============================================================
*/

#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include "DHTesp.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


// ================= WiFi =================
const char* ssid = "Wokwi-GUEST";
const char* password = "";

// ================= ThingSpeak =================
const char* server = "api.thingspeak.com";
const String channelID = "3406001";
const String writeApiKey = "H2HD276YVQHCNY5I";
const String readApiKey  = "UDJ2JHLMJ2UMKP81";

// ================= Pins =================
#define DHTPIN      15
#define LM35_PIN    35
#define LDR_PIN     34
#define PIR_PIN     27
#define TRIG_PIN    5
#define ECHO_PIN    18

#define RGB_R       25
#define RGB_G       26
#define RGB_B       14
#define BUZZER_PIN  23

// ================= OLED =================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHTesp dht;

// ================= Fonctions =================

float readLM35Temperature() {
  int raw = analogRead(LM35_PIN);
  float voltageMV = raw * (3300.0 / 4095.0);
  float temperature = voltageMV / 10.0;
  return temperature;
}

float readLuminosityPercent() {
  int raw = analogRead(LDR_PIN);

  // Selon le montage, tu peux inverser la formule.
  // Ici : raw élevé = lumière élevée.
  float percent = (raw / 4095.0) * 100.0;

  if (percent < 0) percent = 0;
  if (percent > 100) percent = 100;

  return percent;
}

float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {
    return -1;
  }

  float distance = duration * 0.0343 / 2.0;
  return distance;
}

int calculateRiskScore(float tempDHT, float hum, float tempLM35, float light, int motion, float distance) {
  int score = 0;

  if (tempDHT > 35 || tempLM35 > 35) score += 30;
  if (tempDHT > 40 || tempLM35 > 40) score += 20;

  if (hum < 25 || hum > 80) score += 20;

  if (light < 15) score += 10;
  if (light > 90) score += 10;

  if (motion == 1) score += 15;

  if (distance > 0 && distance < 50) score += 25;

  if (score > 100) score = 100;

  return score;
}

int calculateAlertCode(float tempDHT, float hum, float tempLM35, float light, int motion, float distance, int riskScore) {
  /*
    alertCode:
      0 = Normal
      1 = Température élevée
      2 = Humidité anormale
      3 = Luminosité critique
      4 = Mouvement + obstacle proche
      5 = Risque global critique
  */

  if (riskScore >= 75) return 5;
  if (motion == 1 && distance > 0 && distance < 50) return 4;
  if (light < 15 || light > 90) return 3;
  if (hum < 25 || hum > 80) return 2;
  if (tempDHT > 35 || tempLM35 > 35) return 1;

  return 0;
}

void setRGB(int riskScore) {
  if (riskScore < 30) {
    // Vert
    digitalWrite(RGB_R, LOW);
    digitalWrite(RGB_G, HIGH);
    digitalWrite(RGB_B, LOW);
  } else if (riskScore < 70) {
    // Jaune = Rouge + Vert
    digitalWrite(RGB_R, HIGH);
    digitalWrite(RGB_G, HIGH);
    digitalWrite(RGB_B, LOW);
  } else {
    // Rouge
    digitalWrite(RGB_R, HIGH);
    digitalWrite(RGB_G, LOW);
    digitalWrite(RGB_B, LOW);
  }
}

void updateBuzzer(int alertCode) {
  if (alertCode >= 4) {
    tone(BUZZER_PIN, 1000);
  } else {
    noTone(BUZZER_PIN);
  }
}

void updateOLED(float tempDHT, float hum, float tempLM35, float light, int motion, float distance, int riskScore, int alertCode) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);
  display.println("AI Env Monitoring");

  display.setCursor(0, 12);
  display.print("DHT:");
  display.print(tempDHT, 1);
  display.print("C ");
  display.print(hum, 0);
  display.println("%");

  display.setCursor(0, 24);
  display.print("LM35:");
  display.print(tempLM35, 1);
  display.print("C L:");
  display.print(light, 0);
  display.println("%");

  display.setCursor(0, 36);
  display.print("PIR:");
  display.print(motion);
  display.print(" Dist:");
  display.print(distance, 0);
  display.println("cm");

  display.setCursor(0, 48);
  display.print("Risk:");
  display.print(riskScore);
  display.print("% Alert:");
  display.print(alertCode);

  display.display();
}

void sendToThingSpeak(float tempDHT, float hum, float tempLM35, float light, int motion, float distance, int riskScore, int alertCode) {
  WiFiClient client;
  HTTPClient http;

  String payload = "{\"api_key\":\"" + writeApiKey +
                   "\",\"field1\":\"" + String(tempDHT, 1) +
                   "\",\"field2\":\"" + String(hum, 1) +
                   "\",\"field3\":\"" + String(tempLM35, 1) +
                   "\",\"field4\":\"" + String(light, 1) +
                   "\",\"field5\":\"" + String(motion) +
                   "\",\"field6\":\"" + String(distance, 1) +
                   "\",\"field7\":\"" + String(riskScore) +
                   "\",\"field8\":\"" + String(alertCode) +
                   "\"}";

  http.begin(client, server, 80, "/update.json");
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.print("[ThingSpeak] Donnees envoyees. HTTP Code: ");
    Serial.println(httpCode);
  } else {
    Serial.print("[ThingSpeak] Erreur envoi: ");
    Serial.println(httpCode);
  }

  http.end();
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIR_PIN, INPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  pinMode(RGB_R, OUTPUT);
  pinMode(RGB_G, OUTPUT);
  pinMode(RGB_B, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(RGB_R, LOW);
  digitalWrite(RGB_G, LOW);
  digitalWrite(RGB_B, LOW);
  noTone(BUZZER_PIN);

  dht.setup(DHTPIN, DHTesp::DHT22);

  Wire.begin(21, 22);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[OLED] Erreur initialisation OLED");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("Starting system...");
    display.display();
  }

  WiFi.begin(ssid, password);
  Serial.print("Connexion WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Connecte. IP: ");
  Serial.println(WiFi.localIP());

  Serial.println("Systeme initialise.");
}

// ================= LOOP =================
void loop() {
  delay(2000);

  TempAndHumidity dhtData = dht.getTempAndHumidity();

  float tempDHT = dhtData.temperature;
  float humidity = dhtData.humidity;
  float tempLM35 = readLM35Temperature();
  float luminosity = readLuminosityPercent();
  int motion = digitalRead(PIR_PIN);
  float distance = readDistanceCM();

  if (isnan(tempDHT) || isnan(humidity)) {
    Serial.println("[DHT22] Erreur lecture capteur.");
    return;
  }

  int riskScore = calculateRiskScore(tempDHT, humidity, tempLM35, luminosity, motion, distance);
  int alertCode = calculateAlertCode(tempDHT, humidity, tempLM35, luminosity, motion, distance, riskScore);

  setRGB(riskScore);
  updateBuzzer(alertCode);
  updateOLED(tempDHT, humidity, tempLM35, luminosity, motion, distance, riskScore, alertCode);

  Serial.println("========== Environmental Data ==========");
  Serial.print("DHT Temp      : "); Serial.print(tempDHT); Serial.println(" C");
  Serial.print("Humidity      : "); Serial.print(humidity); Serial.println(" %");
  Serial.print("LM35 Temp     : "); Serial.print(tempLM35); Serial.println(" C");
  Serial.print("Luminosity    : "); Serial.print(luminosity); Serial.println(" %");
  Serial.print("Motion        : "); Serial.println(motion);
  Serial.print("Distance      : "); Serial.print(distance); Serial.println(" cm");
  Serial.print("Risk Score    : "); Serial.println(riskScore);
  Serial.print("Alert Code    : "); Serial.println(alertCode);
  Serial.println("========================================");

  sendToThingSpeak(tempDHT, humidity, tempLM35, luminosity, motion, distance, riskScore, alertCode);

  /*
    ThingSpeak limite le rythme d'ecriture.
    On garde 20 secondes pour eviter les conflits.
  */
  delay(20000);
}