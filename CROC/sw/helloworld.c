#include "uart.h"
#include "print.h"
#include "timer.h"
#include "gpio.h"
#include "util.h"
#include "config.h"

#ifndef USER_SENSORS_BASE
#define USER_SENSORS_BASE 0x20000000u
#endif

#define SENSOR_F_OFF       0x00u
#define SENSOR_RF_OFF      0x04u
#define SENSOR_OBI_DMX_OFF  0x08u
#define SENSOR_UART_OFF     0x0Cu

static inline volatile uint32_t* mmio32(uint32_t addr) {
  return (volatile uint32_t*)addr;
}

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

static inline void print_sensors(uint32_t f, uint32_t rf, uint32_t obi_dmx, uint32_t uart) {
  // OBI_DMX and UART are narrower internally; exported as 32-bit words.
  // OBI_DMX: [14:0] valid (15 bits total: 12 main xbar + 3 periph demux)
  // UART:    [18:0] valid (19 bits)
  printf("F: 0x%x | RF: 0x%x | OBI_DMX: 0x%x | UART: 0x%x\r\n", f, rf, obi_dmx, uart);
}

int main(void) {
  uart_init();
  printf("\r\n=== SENSOR MONITOR ===\r\n");
  printf("Hello LESC!!!\r\n");
  uart_write_flush();

  gpio_selftest();
  uart_write_flush();

  // Simple compute
  uint32_t start = get_mcycle();
  uint32_t res   = isqrt_u32(1234567890UL);
  uint32_t end   = get_mcycle();
  printf("Result: 0x%x, Cycles: 0x%x\r\n", res, end - start);
  uart_write_flush();

  volatile uint32_t *sensor_f       = mmio32(USER_SENSORS_BASE + SENSOR_F_OFF);
  volatile uint32_t *sensor_rf      = mmio32(USER_SENSORS_BASE + SENSOR_RF_OFF);
  volatile uint32_t *sensor_obi_dmx = mmio32(USER_SENSORS_BASE + SENSOR_OBI_DMX_OFF);
  volatile uint32_t *sensor_uart    = mmio32(USER_SENSORS_BASE + SENSOR_UART_OFF);

  while (1) {
    uint32_t val_f       = *sensor_f;
    uint32_t val_rf      = *sensor_rf;
    uint32_t val_obi_dmx = *sensor_obi_dmx;
    uint32_t val_uart    = *sensor_uart;

    print_sensors(val_f, val_rf, val_obi_dmx, val_uart);

    printf("burn_regs()\r\n");
    uart_write_flush();
    burn_regs();

    gpio_toggle(0x0F);

    printf("Tick\r\n");
    uart_write_flush();
    sleep_ms(2000);

    printf("Tock\r\n");
    uart_write_flush();
  }

  return 0;
}
