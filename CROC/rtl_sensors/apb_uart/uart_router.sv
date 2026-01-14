`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Module: uart_router
// Description: UART Router for FPGA-Managed Communication (Scientific Research)
//
// ============================================================================
// SYSTEM ARCHITECTURE (Mode 1: FPGA-Managed)
// ============================================================================
//
//     ┌─────────┐                    ┌─────────────────────────────────┐
//     │   PC    │◄══════════════════►│           FPGA                  │
//     │  (App)  │     USB-UART       │  ┌───────┐    ┌─────────────┐  │
//     └─────────┘     115200         │  │ CROC  │◄──►│ uart_router │  │
//                                    │  │RISC-V │    └──────┬──────┘  │
//                                    │  └───────┘           │         │
//                                    └──────────────────────┼─────────┘
//                                                           │
//                                                    ┌──────▼──────┐
//                                                    │   STM32     │
//                                                    │    MCU      │
//                                                    └─────────────┘
//
// ============================================================================
// ROUTING PROTOCOL
// ============================================================================
// PC → Devices (Forward Path):
//   - Header 0x10 + payload → Strip header, forward to CROC only
//   - Header 0x20 + payload → Strip header, forward to STM32 only
//   - No header (printable) → Forward to CROC (default for terminal input)
//
// Devices → PC (Return Path):
//   - CROC TX: Sensor data + debug printf (continuous, HIGH priority)
//   - STM32 TX: Protocol responses (on-demand, LOW priority)
//   - Arbitration: CROC wins if active, STM32 during CROC idle gaps
//
// ============================================================================
// TIMING (115200 baud)
// ============================================================================
//   - Bit time: 8.68µs
//   - Byte time: 86.8µs (10 bits)
//   - Arbitration timeout: 1ms (releases lock after inactivity)
//
//////////////////////////////////////////////////////////////////////////////////

module uart_router #(
    parameter int CLK_FREQ   = 20_000_000,  // System clock frequency (Hz)
    parameter int BAUD_RATE  = 115_200,     // UART baud rate
    parameter int TIMEOUT_MS = 1            // Arbitration timeout (ms)
)(
    input  logic clk,
    input  logic rst_n,

    // =========================================================================
    // PC Interface (USB-UART Bridge)
    // =========================================================================
    input  logic pc_rx,          // PC TX → FPGA RX (data from PC)
    output logic pc_tx,          // FPGA TX → PC RX (data to PC)

    // =========================================================================
    // CROC Interface (RISC-V Softcore Internal UART)
    // =========================================================================
    output logic croc_rx,        // Router → CROC RX (commands to CROC)
    input  logic croc_tx,        // CROC TX → Router (sensor data + debug)

    // =========================================================================
    // STM32 Interface (External MCU)
    // =========================================================================
    output logic stm_rx,         // Router → STM32 RX (commands to STM32)
    input  logic stm_tx          // STM32 TX → Router (responses from STM32)
);

    // =========================================================================
    // Constants
    // =========================================================================
    localparam logic [7:0] HEADER_CROC = 8'h10;
    localparam logic [7:0] HEADER_STM  = 8'h20;
    
    // Timing calculations
    localparam int CYCLES_PER_BIT  = CLK_FREQ / BAUD_RATE;
    localparam int TIMEOUT_CYCLES  = (CLK_FREQ / 1000) * TIMEOUT_MS;
    localparam int BYTE_CYCLES     = CYCLES_PER_BIT * 10;  // 10 bits per byte

    // =========================================================================
    // Input Synchronizers (2-stage for metastability)
    // =========================================================================
    logic pc_rx_ff1, pc_rx_sync;
    logic croc_tx_ff1, croc_tx_sync;
    logic stm_tx_ff1, stm_tx_sync;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc_rx_ff1    <= 1'b1;
            pc_rx_sync   <= 1'b1;
            croc_tx_ff1  <= 1'b1;
            croc_tx_sync <= 1'b1;
            stm_tx_ff1   <= 1'b1;
            stm_tx_sync  <= 1'b1;
        end else begin
            pc_rx_ff1    <= pc_rx;
            pc_rx_sync   <= pc_rx_ff1;
            croc_tx_ff1  <= croc_tx;
            croc_tx_sync <= croc_tx_ff1;
            stm_tx_ff1   <= stm_tx;
            stm_tx_sync  <= stm_tx_ff1;
        end
    end

    // =========================================================================
    // FORWARD PATH: PC → Devices
    // =========================================================================
    // Strategy: Receive first byte to check for routing header
    // - If 0x10: Route remaining bytes to CROC only
    // - If 0x20: Route remaining bytes to STM32 only  
    // - Otherwise: Route to CROC (default for terminal/debug)
    //
    // Implementation: Simple bit-level UART receiver for header detection
    // After header, transparent forwarding of remaining bits
    
    typedef enum logic [2:0] {
        FWD_IDLE,
        FWD_START_BIT,
        FWD_DATA_BITS,
        FWD_STOP_BIT,
        FWD_ROUTING
    } fwd_state_t;
    
    fwd_state_t fwd_state;
    
    logic [15:0] fwd_bit_timer;
    logic [3:0]  fwd_bit_cnt;
    logic [7:0]  fwd_shift_reg;
    logic        fwd_header_valid;
    logic        fwd_route_to_stm;
    logic        fwd_route_to_croc;
    logic [19:0] fwd_route_timeout;
    
    // Transparent forwarding control
    logic fwd_transparent_mode;
    logic fwd_suppress_to_croc;
    logic fwd_suppress_to_stm;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fwd_state          <= FWD_IDLE;
            fwd_bit_timer      <= '0;
            fwd_bit_cnt        <= '0;
            fwd_shift_reg      <= '0;
            fwd_header_valid   <= 1'b0;
            fwd_route_to_stm   <= 1'b0;
            fwd_route_to_croc  <= 1'b1;  // Default: CROC
            fwd_route_timeout  <= '0;
            fwd_transparent_mode <= 1'b0;
            fwd_suppress_to_croc <= 1'b0;
            fwd_suppress_to_stm  <= 1'b1;  // Default: don't send to STM
        end else begin
            case (fwd_state)
                FWD_IDLE: begin
                    // Wait for start bit (falling edge)
                    if (pc_rx_sync == 1'b0) begin
                        fwd_state     <= FWD_START_BIT;
                        fwd_bit_timer <= CYCLES_PER_BIT / 2;  // Sample at middle
                        fwd_bit_cnt   <= '0;
                        
                        // If we're in transparent mode, just pass through
                        if (fwd_transparent_mode) begin
                            fwd_route_timeout <= TIMEOUT_CYCLES;
                        end else begin
                            // First byte - need to check header
                            fwd_header_valid <= 1'b0;
                        end
                    end
                    
                    // Timeout: return to default routing after gap
                    if (fwd_transparent_mode) begin
                        if (fwd_route_timeout > 0) begin
                            fwd_route_timeout <= fwd_route_timeout - 1;
                        end else begin
                            // Timeout - return to header detection mode
                            fwd_transparent_mode <= 1'b0;
                            fwd_route_to_croc    <= 1'b1;
                            fwd_route_to_stm     <= 1'b0;
                            fwd_suppress_to_croc <= 1'b0;
                            fwd_suppress_to_stm  <= 1'b1;
                        end
                    end
                end
                
                FWD_START_BIT: begin
                    if (fwd_bit_timer > 0) begin
                        fwd_bit_timer <= fwd_bit_timer - 1;
                    end else begin
                        // Verify start bit is still low
                        if (pc_rx_sync == 1'b0) begin
                            fwd_state     <= FWD_DATA_BITS;
                            fwd_bit_timer <= CYCLES_PER_BIT;
                            fwd_bit_cnt   <= '0;
                        end else begin
                            // False start, return to idle
                            fwd_state <= FWD_IDLE;
                        end
                    end
                end
                
                FWD_DATA_BITS: begin
                    if (fwd_bit_timer > 0) begin
                        fwd_bit_timer <= fwd_bit_timer - 1;
                    end else begin
                        // Sample data bit (LSB first)
                        fwd_shift_reg <= {pc_rx_sync, fwd_shift_reg[7:1]};
                        fwd_bit_cnt   <= fwd_bit_cnt + 1;
                        fwd_bit_timer <= CYCLES_PER_BIT;
                        
                        if (fwd_bit_cnt == 4'd7) begin
                            fwd_state <= FWD_STOP_BIT;
                        end
                    end
                end
                
                FWD_STOP_BIT: begin
                    if (fwd_bit_timer > 0) begin
                        fwd_bit_timer <= fwd_bit_timer - 1;
                    end else begin
                        // Byte complete - check if it's a header
                        if (!fwd_transparent_mode) begin
                            // First byte after idle - check for routing header
                            if (fwd_shift_reg == HEADER_CROC) begin
                                // Route to CROC, suppress header
                                fwd_route_to_croc    <= 1'b1;
                                fwd_route_to_stm     <= 1'b0;
                                fwd_suppress_to_croc <= 1'b0;
                                fwd_suppress_to_stm  <= 1'b1;
                                fwd_transparent_mode <= 1'b1;
                                fwd_header_valid     <= 1'b1;
                            end else if (fwd_shift_reg == HEADER_STM) begin
                                // Route to STM32, suppress header
                                fwd_route_to_croc    <= 1'b0;
                                fwd_route_to_stm     <= 1'b1;
                                fwd_suppress_to_croc <= 1'b1;
                                fwd_suppress_to_stm  <= 1'b0;
                                fwd_transparent_mode <= 1'b1;
                                fwd_header_valid     <= 1'b1;
                            end else begin
                                // No header - route to CROC by default
                                // This byte should be forwarded (not suppressed)
                                fwd_route_to_croc    <= 1'b1;
                                fwd_route_to_stm     <= 1'b0;
                                fwd_suppress_to_croc <= 1'b0;
                                fwd_suppress_to_stm  <= 1'b1;
                                fwd_transparent_mode <= 1'b1;
                                fwd_header_valid     <= 1'b0;
                            end
                        end
                        
                        fwd_route_timeout <= TIMEOUT_CYCLES;
                        fwd_state <= FWD_IDLE;
                    end
                end
                
                default: fwd_state <= FWD_IDLE;
            endcase
        end
    end
    
    // Forward path output logic
    // During header byte (first byte, transparent_mode=0): suppress all outputs
    // After header detected: forward based on routing decision
    // If no header: forward to CROC
    
    logic suppress_current_byte;
    assign suppress_current_byte = !fwd_transparent_mode || 
                                   (fwd_header_valid && fwd_state != FWD_IDLE);
    
    // CROC receives: PC data when routed to CROC
    assign croc_rx = (fwd_route_to_croc && !fwd_suppress_to_croc) ? pc_rx_sync : 1'b1;
    
    // STM32 receives: PC data when routed to STM32
    assign stm_rx = (fwd_route_to_stm && !fwd_suppress_to_stm) ? pc_rx_sync : 1'b1;

    // =========================================================================
    // RETURN PATH: Devices → PC (Arbitration)
    // =========================================================================
    // Priority: CROC > STM32
    // CROC sends continuous sensor data, STM32 sends occasional responses
    // Use start-bit detection and timeout-based arbitration
    
    typedef enum logic [1:0] {
        ARB_IDLE,
        ARB_CROC,
        ARB_STM
    } arb_state_t;
    
    arb_state_t arb_state;
    
    logic [19:0] arb_timeout;
    logic croc_tx_prev, stm_tx_prev;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            arb_state    <= ARB_IDLE;
            arb_timeout  <= '0;
            croc_tx_prev <= 1'b1;
            stm_tx_prev  <= 1'b1;
        end else begin
            croc_tx_prev <= croc_tx_sync;
            stm_tx_prev  <= stm_tx_sync;
            
            case (arb_state)
                ARB_IDLE: begin
                    arb_timeout <= '0;
                    
                    // Priority: CROC first
                    if (croc_tx_sync == 1'b0) begin
                        arb_state <= ARB_CROC;
                    end else if (stm_tx_sync == 1'b0) begin
                        arb_state <= ARB_STM;
                    end
                end
                
                ARB_CROC: begin
                    // Reset timeout on any edge (activity)
                    if (croc_tx_sync != croc_tx_prev) begin
                        arb_timeout <= '0;
                    end else if (arb_timeout < TIMEOUT_CYCLES) begin
                        arb_timeout <= arb_timeout + 1;
                    end else begin
                        // Timeout - release lock
                        arb_state <= ARB_IDLE;
                    end
                end
                
                ARB_STM: begin
                    // Reset timeout on activity
                    if (stm_tx_sync != stm_tx_prev) begin
                        arb_timeout <= '0;
                    end else if (arb_timeout < TIMEOUT_CYCLES) begin
                        arb_timeout <= arb_timeout + 1;
                    end else begin
                        arb_state <= ARB_IDLE;
                    end
                end
                
                default: arb_state <= ARB_IDLE;
            endcase
        end
    end
    
    // Return path output mux
    always_comb begin
        case (arb_state)
            ARB_CROC: pc_tx = croc_tx_sync;
            ARB_STM:  pc_tx = stm_tx_sync;
            default:  pc_tx = 1'b1;  // Idle high
        endcase
    end

endmodule
