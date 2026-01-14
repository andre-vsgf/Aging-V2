/**
 * @file    helloworld.c
 * @brief   CROC Sensor Monitor Firmware with XADC Support
 * 
 * This firmware reads aging sensor data from the user_sensor_monitor peripheral
 * and outputs it via UART. For scientific research applications.
 * 
 * Output Format (text-based, human-readable):
 *   F: 0x<alarm_f> | RF: 0x<alarm_rf>
 * 
 * The PC application parses these hex values from the UART stream.
 * XADC temperature/voltage can be added when the System Monitor peripheral
 * is properly integrated into the OBI bus.
 */

#include "uart.h"
#include "print.h"
#include "timer.h"
#include "gpio.h"
#include "util.h"
#include "config.h"

// ===========================================================================
// User Domain Sensor Monitor Peripheral (OBI-accessible)
// ===========================================================================
// Base address as defined in user_pkg.sv and user_sensor_monitor.sv
#ifndef USER_SENSORS_BASE
#define USER_SENSORS_BASE 0x20000000
#endif

// Register offsets
#define SENSOR_ALARM_F_OFFSET   0x00    // AM sensor alarm bitmap (RO)
#define SENSOR_ALARM_RF_OFFSET  0x04    // LF sensor alarm bitmap (RO)
#define SENSOR_STATUS_OFFSET    0x08    // Status register (RO)
#define SENSOR_CTRL_OFFSET      0x0C    // Control register (RW)

// Status register bits
#define STATUS_VALID_BIT        0x01
#define STATUS_AM_ACTIVE_BIT    0x02
#define STATUS_LF_ACTIVE_BIT    0x04

// ===========================================================================
// Helper Macros
// ===========================================================================
#define SENSOR_REG(offset) (*(volatile uint32_t *)(USER_SENSORS_BASE + (offset)))

#define READ_ALARM_F()      SENSOR_REG(SENSOR_ALARM_F_OFFSET)
#define READ_ALARM_RF()     SENSOR_REG(SENSOR_ALARM_RF_OFFSET)
#define READ_STATUS()       SENSOR_REG(SENSOR_STATUS_OFFSET)

// ===========================================================================
// Utility: Count set bits (population count)
// ===========================================================================
static inline uint32_t popcount(uint32_t x) {
    uint32_t count = 0;
    while (x) {
        count += x & 1;
        x >>= 1;
    }
    return count;
}

// ===========================================================================
// Main Program
// ===========================================================================
int main() {
    // Initialize UART
    uart_init();
    
    // Startup banner
    printf("\r\n");
    printf("================================\r\n");
    printf("  CROC Aging Sensor Monitor\r\n");
    printf("  Scientific Research System\r\n");
    printf("================================\r\n");
    printf("\r\n");

    // Main monitoring loop
    while (1) {
        // Read sensor data from OBI peripheral
        uint32_t alarm_f  = READ_ALARM_F();
        uint32_t alarm_rf = READ_ALARM_RF();
        uint32_t status   = READ_STATUS();
        
        // Count active alarms
        uint32_t f_count  = popcount(alarm_f);
        uint32_t rf_count = popcount(alarm_rf);
        
        // Output format: Easy to parse, includes raw hex and counts
        // Format: "F: 0x<hex> (<count>) | RF: 0x<hex> (<count>)"
        printf("F: 0x%x | RF: 0x%x\r\n", alarm_f, alarm_rf);
        
        // Toggle GPIO to indicate activity (heartbeat)
        gpio_toggle(0x01);
        
        // Wait 1 second before next reading
        sleep_ms(1000);
    }
    
    return 0;
}

