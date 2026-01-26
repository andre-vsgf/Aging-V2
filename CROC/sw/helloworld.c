/**
 * @file    helloworld.c
 * @brief   CROC Sensor Monitor Firmware
 * 
 * This firmware reads aging sensor data from the user_sensor_monitor peripheral
 * and outputs it via UART. For scientific research applications.
 * 
 * Output Format:
 *   F: 0x<hex> | RF: 0x<hex> | OBI: 0x<hex> | UART: 0x<hex>
 * 
 * The PC application parses these hex values from the UART stream.
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

// Register offsets (must match user_sensor_monitor.sv)
#define SENSOR_ALARM_F_OFFSET   0x00    // AM sensor alarm bitmap (RO)
#define SENSOR_ALARM_RF_OFFSET  0x04    // LF sensor alarm bitmap (RO)
#define SENSOR_ALARM_OBI_OFFSET 0x08    // OBI_DMX sensor (RO)
#define SENSOR_ALARM_UART_OFFSET 0x0C   // UART sensor (RO)
#define SENSOR_STATUS_OFFSET    0x10    // Status register (RO)
#define SENSOR_CTRL_OFFSET      0x14    // Control register (RW)

// Status register bits
#define STATUS_VALID_BIT        0x01
#define STATUS_AM_ACTIVE_BIT    0x02
#define STATUS_LF_ACTIVE_BIT    0x04
#define STATUS_OBI_ACTIVE_BIT   0x08
#define STATUS_UART_ACTIVE_BIT  0x10

// ===========================================================================
// Helper Macros
// ===========================================================================
#define SENSOR_REG(offset) (*(volatile uint32_t *)(USER_SENSORS_BASE + (offset)))

#define READ_ALARM_F()      SENSOR_REG(SENSOR_ALARM_F_OFFSET)
#define READ_ALARM_RF()     SENSOR_REG(SENSOR_ALARM_RF_OFFSET)
#define READ_ALARM_OBI()    SENSOR_REG(SENSOR_ALARM_OBI_OFFSET)
#define READ_ALARM_UART()   SENSOR_REG(SENSOR_ALARM_UART_OFFSET)
#define READ_STATUS()       SENSOR_REG(SENSOR_STATUS_OFFSET)

// Integer square root (example workload)
static uint32_t isqrt_u32(uint32_t n) {
  uint32_t res = 0;
  uint32_t bit = (uint32_t)1u << 30;

  while (bit > n) bit >>= 2;

  while (bit) {
    if (n >= res + bit) {
      n -= res + bit;
      res = (res >> 1) + bit;
    } else {
      res >>= 1;
    }
    bit >>= 2;
  }
  return res;
}

volatile uint32_t sink;

static inline void burn_regs(void) {
  uint32_t a = 0x12345678u;
  uint32_t b = 0x9abcdef0u;
  uint32_t c = 0x0f0f0f0fu;

  for (uint32_t i = 0; i < 200000u; i++) {
    a = a * 1664525u + 1013904223u;
    b ^= a + 0x9e3779b9u;
    c += (b ^ (a >> 3));

    sink = a ^ b ^ c;
    asm volatile("" ::: "memory");
  }
}

static inline void gpio_selftest(void) {
  gpio_set_direction(0xFFFF, 0x000F); // lowest 4 as outputs
  gpio_enable(0x00FF);                // enable lowest 8

  gpio_write(0x0A);
  asm volatile("nop; nop; nop; nop; nop;");
  printf("GPIO (expect 0xA0): 0x%x\r\n", gpio_read());

  gpio_toggle(0x0F);
  asm volatile("nop; nop; nop; nop; nop;");
  printf("GPIO (expect 0x50): 0x%x\r\n", gpio_read());
}

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
// Print hex with leading zeros (8 digits)
// ===========================================================================
static void print_hex32(uint32_t val) {
    /* Emite 8 nibbles via %x, garantindo sempre 8 dígitos.
     */
    for (int shift = 28; shift >= 0; shift -= 4) {
        uint32_t nib = (val >> (uint32_t)shift) & 0xFu;
        printf("%x", nib);
    }
}


// ===========================================================================
// Main Program
// ===========================================================================
int main() {
    // Initialize UART
    uart_init();
    
    // Wait for UART to stabilize
    sleep_ms(100);
    
    // Startup banner
    printf("\r\n");
    printf("================================\r\n");
    printf("  CROC Aging Sensor Monitor\r\n");
    printf("  Scientific Research System\r\n");
    printf("================================\r\n");
    printf("\r\n");

    gpio_selftest();
    uart_write_flush();

    // Main monitoring loop
    while (1) {
        // Read sensor data from OBI peripheral
        uint32_t alarm_f    = READ_ALARM_F();
        uint32_t alarm_rf   = READ_ALARM_RF();
        uint32_t alarm_obi  = READ_ALARM_OBI();
        uint32_t alarm_uart = READ_ALARM_UART();
        
        uart_write_flush();
        burn_regs();
        // Output format matching router.py expectations:
        // "F: 0xXXXXXXXX | RF: 0xXXXXXXXX | OBI: 0xXXXXXXXX | UART: 0xXXXXXXXX"
        printf("F: 0x");
        print_hex32(alarm_f);
        printf(" | RF: 0x");
        print_hex32(alarm_rf);
        printf(" | OBI: 0x");
        print_hex32(alarm_obi);
        printf(" | UART: 0x");
        print_hex32(alarm_uart);
        printf("\r\n");
        
        // Toggle GPIO to indicate activity (heartbeat)
        gpio_toggle(0x01);
        
        // Wait 1 second before next reading
        sleep_ms(1000);
    }
    
    return 0;
}

// Minimal memcpy implementation for bare-metal
typedef unsigned long size_t;
void *memcpy(void *dest, const void *src, size_t n) {
    char *d = (char *)dest;
    const char *s = (const char *)src;
    while (n--) {
        *d++ = *s++;
    }
    return dest;
}