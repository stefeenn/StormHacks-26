#include <LiquidCrystal.h>

// LCD: RS, E, D4, D5, D6, D7
LiquidCrystal lcd(12, 11, 7, 6, 5, 4);

// Joystick
const int joystickX = A0;
const int joystickButton = 2;

String choice = "NONE";
bool buttonWasPressed = false;

void setup() {
  Serial.begin(9600);
  pinMode(joystickButton, INPUT_PULLUP);

  lcd.begin(16, 2);

  lcd.setCursor(0, 0);
  lcd.print("Pred: 94.5 mph");

  lcd.setCursor(0, 1);
  lcd.print("Choose O/U");
}

void loop() {
  int x = analogRead(joystickX);
  int button = digitalRead(joystickButton);

  // -X direction
  if (x < 300 && choice != "OVER") {
    choice = "OVER";

    lcd.setCursor(0, 1);
    lcd.print("> OVER          ");
  }

  // +X direction
  else if (x > 700 && choice != "UNDER") {
    choice = "UNDER";

    lcd.setCursor(0, 1);
    lcd.print("> UNDER         ");
  }

  // Joystick pressed
  if (button == LOW && !buttonWasPressed) {
    buttonWasPressed = true;

    if (choice != "NONE") {
      Serial.print("CHOICE:");
      Serial.println(choice);

      lcd.setCursor(0, 1);
      lcd.print("LOCKED: ");
      lcd.print(choice);
      lcd.print("     ");
    }
  }

  // Allow another press after releasing joystick
  if (button == HIGH) {
    buttonWasPressed = false;
  }

  delay(50);
}