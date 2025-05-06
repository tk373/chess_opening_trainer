import sys
import chess
import chess.svg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QPushButton, QComboBox, QProgressBar, QFrame)
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QCursor, QImage
import os
import time
from config import (
    BOARD_SIZE,
    EXTRA_SPACE,
    SIZE,
    MARGIN,
    SQUARE_SIZE,
    board,
    stockfish,
    BOARD_LOCK,
    OPENING_MOVES,
    SELECTED_LINE,
    SELECTED_OPENING,
    SCALING_FACTOR,
)

# Debug function
def debug_print(message):
    print(f"DEBUG: {message}")
    sys.stdout.flush()  # Force output to appear immediately

class EvalBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.white_eval = 0.0
        self.black_eval = 0.0
        self.setMinimumHeight(40)
        self.setMaximumHeight(40)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        
        # Convert evaluation to a ratio
        if isinstance(self.white_eval, str):
            # Handle mate scores
            if self.white_eval.startswith('M'):
                white_ratio = 1.0 if not self.white_eval[1] == '-' else 0.0
        else:
            max_eval = 10
            min_eval = -10
            white_ratio = max(min((self.white_eval + max_eval) / (max_eval - min_eval), 1.0), 0.0)
        
        black_ratio = 1.0 - white_ratio
        
        # Draw white part
        white_width = int(width * white_ratio)
        painter.fillRect(0, 0, white_width, height, QColor(255, 255, 255))
        
        # Draw black part
        black_width = int(width * black_ratio)
        painter.fillRect(white_width, 0, black_width, height, QColor(0, 0, 0))
        
        # Draw outline
        painter.setPen(QPen(Qt.black, 3))
        painter.drawRect(0, 0, width-1, height-1)
        
    def set_eval(self, white_eval, black_eval):
        self.white_eval = white_eval
        self.black_eval = black_eval
        self.update()

class ChessBoard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.selected_square = None
        self.dragging_piece = None
        self.dragging_pixmap = None
        self.drag_position = None
        self.possible_moves = None
        self.opening_index = 0
        self.in_opening_phase = True
        self.show_dragged_piece = False
        self.debug_count = 0
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)  # Space between components
        
        # Create the board widget with a border for visibility
        self.board_widget = QWidget()
        self.board_widget.setFixedSize(BOARD_SIZE, BOARD_SIZE)
        self.board_widget.setStyleSheet("border: 2px solid black;")
        main_layout.addWidget(self.board_widget)
        
        # Create SVG widget for the board
        board_layout = QVBoxLayout(self.board_widget)
        board_layout.setContentsMargins(0, 0, 0, 0)
        self.svg_widget = QSvgWidget(self.board_widget)
        self.svg_widget.setFixedSize(BOARD_SIZE, BOARD_SIZE)
        board_layout.addWidget(self.svg_widget)
        
        # Create evaluation bar
        self.eval_bar = EvalBar()
        main_layout.addWidget(self.eval_bar)
        
        # Create evaluation text label
        self.eval_text = QLabel("White: 0.00 | Black: 0.00")
        self.eval_text.setAlignment(Qt.AlignCenter)
        self.eval_text.setStyleSheet("background-color: white; font-weight: bold; font-size: 12pt; border: 1px solid black;")
        main_layout.addWidget(self.eval_text)
        
        # Create opening info label
        self.opening_info = QLabel("Opening: (None selected)")
        self.opening_info.setAlignment(Qt.AlignCenter)
        self.opening_info.setStyleSheet("background-color: white; font-weight: bold; font-size: 12pt; border: 1px solid black;")
        main_layout.addWidget(self.opening_info)
        
        # Debug label
        self.debug_label = QLabel("Debug: No piece dragging")
        self.debug_label.setAlignment(Qt.AlignCenter)
        self.debug_label.setStyleSheet("background-color: yellow; color: black; font-weight: bold;")
        main_layout.addWidget(self.debug_label)
        
        # Initialize the board
        self.update_board()
        self.analyze_position()
        
        # Enable mouse tracking and install custom event handling
        self.board_widget.setMouseTracking(True)
        self.board_widget.installEventFilter(self)
        
        # Save original paint event for board_widget
        self.original_paint_event = self.board_widget.paintEvent
        
        # Override paint event
        def custom_paint_event(event):
            debug_print(f"Custom paint event called: {self.debug_count}")
            self.debug_count += 1
            
            # First paint the SVG widget (the board)
            painter = QPainter(self.board_widget)
            self.svg_widget.render(painter)
            
            # Then paint our dragged piece if needed
            if self.show_dragged_piece and self.dragging_piece and self.drag_position and self.dragging_pixmap:
                debug_print(f"Drawing piece at {self.drag_position.x()}, {self.drag_position.y()}")
                piece_x = int(self.drag_position.x() - self.dragging_pixmap.width() // 2)
                piece_y = int(self.drag_position.y() - self.dragging_pixmap.height() // 2)
                
                # Remove the red circle, just draw the piece
                painter.drawPixmap(piece_x, piece_y, self.dragging_pixmap)
                
                # Update debug info
                self.debug_label.setText(f"Piece at ({piece_x}, {piece_y}), size: {self.dragging_pixmap.width()}x{self.dragging_pixmap.height()}")
            else:
                # Update debug info with state
                states = []
                if not self.show_dragged_piece: states.append("show_dragged_piece=False")
                if not self.dragging_piece: states.append("dragging_piece=None")
                if not self.drag_position: states.append("drag_position=None") 
                if not self.dragging_pixmap: states.append("dragging_pixmap=None")
                self.debug_label.setText(f"Not drawing piece: {', '.join(states)}")
                
            painter.end()
        
        # Assign custom paint event
        self.board_widget.paintEvent = custom_paint_event
        
    def eventFilter(self, obj, event):
        if obj == self.board_widget:
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                debug_print("Mouse press detected")
                self.handle_mouse_press(event)
                return True
            elif event.type() == event.MouseButtonRelease and event.button() == Qt.LeftButton:
                debug_print("Mouse release detected")
                self.handle_mouse_release(event)
                return True
            elif event.type() == event.MouseMove and self.dragging_piece:
                # Only log occasionally to avoid flooding
                if self.debug_count % 10 == 0:
                    debug_print(f"Mouse move: {event.x()}, {event.y()}")
                self.handle_mouse_move(event)
                return True
        return super().eventFilter(obj, event)
    
    def update_board(self, dragging_square=None):
        # Generate SVG with the dragging piece hidden if we're dragging
        last_move = board.peek() if board.move_stack else None
        check_square = board.king(board.turn) if board.is_check() else None
        
        # If we're dragging a piece, remove it from the board view
        if dragging_square is not None:
            debug_print(f"Updating board with dragging_square={dragging_square}")
            # Create a temporary board for drawing
            temp_board = chess.Board(board.fen())
            # Remove the piece being dragged
            temp_board.remove_piece_at(dragging_square)
            # Generate SVG showing the board without the dragged piece
            svg_data = chess.svg.board(
                temp_board,
                size=BOARD_SIZE,
                coordinates=True,
                lastmove=last_move,
                check=check_square
            )
        else:
            # Regular board update
            svg_data = chess.svg.board(
                board,
                size=BOARD_SIZE,
                coordinates=True,
                lastmove=last_move,
                check=check_square
            )
            
        self.svg_widget.load(bytes(svg_data, 'utf-8'))
        
        # Update opening info
        current_opening = SELECTED_OPENING
        current_line_name = "Unknown"
        if hasattr(self.parent_window, 'opening_selector') and hasattr(self.parent_window, 'line_selector'):
            current_opening = self.parent_window.opening_selector.currentText()
            current_line_name = self.parent_window.line_selector.currentText()
        
        # Update opening info label
        moves_left = len(SELECTED_LINE['moves']) - self.opening_index if SELECTED_LINE and 'moves' in SELECTED_LINE else 0
        self.opening_info.setText(f"Opening: {current_opening} - {current_line_name} (Moves Left: {moves_left})")
        
    def handle_mouse_press(self, event):
        x, y = event.x(), event.y()
        file = int(x / SQUARE_SIZE)
        rank = 7 - int(y / SQUARE_SIZE)
        
        debug_print(f"Mouse press at ({x}, {y}) -> square ({file}, {rank})")
        
        if 0 <= file < 8 and 0 <= rank < 8:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            
            if piece and piece.color == board.turn:
                debug_print(f"Selected piece: {piece.symbol()} at square {square}")
                self.selected_square = square
                self.dragging_piece = piece
                
                try:
                    # Create a custom cursor with the piece image
                    debug_print("Creating pixmap for cursor")
                    square_size_int = int(SQUARE_SIZE)
                    
                    # Create a transparent pixmap for the cursor
                    self.dragging_pixmap = QPixmap(square_size_int, square_size_int)
                    self.dragging_pixmap.fill(Qt.transparent)  # Use transparent instead of red
                    
                    # Draw the chess piece on the transparent background
                    painter = QPainter(self.dragging_pixmap)
                    
                    # Get piece SVG content
                    piece_svg = chess.svg.piece(piece, size=square_size_int)
                    
                    # Create a renderer and render the SVG
                    renderer = QSvgRenderer(bytes(piece_svg, 'utf-8'))
                    renderer.render(painter)
                    painter.end()
                    
                    # Save the pixmap for debugging
                    debug_file = "debug_piece.png"
                    self.dragging_pixmap.save(debug_file)
                    debug_print(f"Saved debug pixmap to {debug_file}, exists: {os.path.exists(debug_file)}")
                    
                    # Update cursor position and show the dragged piece
                    self.drag_position = QPoint(x, y)
                    self.show_dragged_piece = True
                    debug_print("Set show_dragged_piece to True")
                    
                    # Update board to remove the dragged piece from its original square
                    self.update_board(square)
                    
                    # Only show legal moves that follow the opening
                    if self.in_opening_phase and board.turn == chess.WHITE:
                        self.possible_moves = []
                        if self.opening_index < len(SELECTED_LINE['moves']):
                            expected_move = chess.Move.from_uci(SELECTED_LINE['moves'][self.opening_index])
                            if expected_move.from_square == square:
                                self.possible_moves = [expected_move.to_square]
                                debug_print(f"Expected move: {expected_move.uci()}")
                    else:
                        self.possible_moves = [move.to_square for move in board.legal_moves if move.from_square == square]
                    
                    # USE A CUSTOM CURSOR
                    # Create a custom cursor that's definitely visible
                    custom_cursor = QCursor(self.dragging_pixmap)
                    self.board_widget.setCursor(custom_cursor)
                    debug_print("Set custom cursor")
                    
                    # Force redraw
                    self.board_widget.update()
                    debug_print("Forced redraw")
                    
                except Exception as e:
                    debug_print(f"Error setting up dragging: {e}")
                    self.selected_square = None
                    self.dragging_piece = None
                    self.show_dragged_piece = False
    
    def handle_mouse_move(self, event):
        if self.dragging_piece:
            # Update the position of the dragged piece
            self.drag_position = QPoint(event.x(), event.y())
            if self.debug_count % 10 == 0:  # Only log occasionally
                debug_print(f"Updated drag position to {event.x()}, {event.y()}")
            # Redraw the board
            self.board_widget.update()
    
    def handle_mouse_release(self, event):
        if self.selected_square is None:
            debug_print("Mouse release but no selected square")
            return
            
        debug_print("Mouse release with selected square")
        x, y = event.x(), event.y()
        file = int(x / SQUARE_SIZE)
        rank = 7 - int(y / SQUARE_SIZE)
        
        debug_print(f"Mouse release at ({x}, {y}) -> square ({file}, {rank})")
        
        # Stop showing the dragged piece
        self.show_dragged_piece = False
        
        # Restore default cursor
        self.board_widget.setCursor(Qt.ArrowCursor)
        
        if 0 <= file < 8 and 0 <= rank < 8:
            target_square = chess.square(file, rank)
            move = chess.Move(self.selected_square, target_square)
            debug_print(f"Attempting move {move.uci()}")
            
            # Process move according to game rules
            self.process_move(move)
        else:
            # Dropped outside the board, just restore the view
            debug_print("Dropped outside board, restoring view")
            self.update_board()
        
        # Reset dragging state
        self.selected_square = None
        self.dragging_piece = None
        self.dragging_pixmap = None
        self.drag_position = None
        self.possible_moves = None
        debug_print("Reset dragging state")
        
        # Redraw the board
        self.board_widget.update()

    def process_move(self, move):
        # Check if the move is legal and follows the opening
        if self.in_opening_phase and board.turn == chess.WHITE:
            if self.opening_index < len(SELECTED_LINE['moves']):
                expected_move = chess.Move.from_uci(SELECTED_LINE['moves'][self.opening_index])
                if move == expected_move:
                    board.push(move)
                    self.opening_index += 1
                    self.update_board()
                    self.analyze_position()
                    
                    # If it's black's turn, make the next opening move for black
                    if board.turn == chess.BLACK and self.in_opening_phase:
                        if self.opening_index < len(SELECTED_LINE['moves']):
                            next_move = chess.Move.from_uci(SELECTED_LINE['moves'][self.opening_index])
                            board.push(next_move)
                            self.opening_index += 1
                            self.update_board()
                            self.analyze_position()
                            
                            # Check if opening is complete after black's move
                            if self.opening_index >= len(SELECTED_LINE['moves']):
                                self.in_opening_phase = False
                                print("Opening phase completed!")
                        else:
                            # Opening completed, switch to Stockfish
                            self.in_opening_phase = False
                            print("Opening phase completed!")
                            self.make_stockfish_move()
                else:
                    # Wrong move for the opening
                    print(f"Incorrect move! Expected {expected_move.uci()} to follow the opening.")
                    # Show the board with all pieces (restore the piece that was being dragged)
                    self.update_board()
            else:
                # Opening completed, switch to regular play
                self.in_opening_phase = False
                if move in board.legal_moves:
                    board.push(move)
                    self.update_board()
                    self.analyze_position()
                    
                    # If it's black's turn, let Stockfish make a move
                    if board.turn == chess.BLACK:
                        self.make_stockfish_move()
                else:
                    # Illegal move, restore the board
                    self.update_board()
        else:
            # Not in opening phase or it's not white's turn
            if move in board.legal_moves:
                board.push(move)
                self.update_board()
                self.analyze_position()
                
                # If it's black's turn, let Stockfish make a move
                if board.turn == chess.BLACK:
                    self.make_stockfish_move()
            else:
                # Illegal move, restore the board
                self.update_board()

    def analyze_position(self):
        with BOARD_LOCK:
            stockfish.set_fen_position(board.fen())
            try:
                evaluation = stockfish.get_evaluation()
                if evaluation['type'] == 'cp':
                    white_eval = evaluation['value'] / 100.0
                    black_eval = -white_eval
                    self.eval_text.setText(f"White: {white_eval:.2f} | Black: {black_eval:.2f}")
                elif evaluation['type'] == 'mate':
                    if evaluation['value'] > 0:
                        white_eval = f"M{evaluation['value']}"
                        black_eval = f"M{-evaluation['value']}"
                    else:
                        white_eval = f"M{-evaluation['value']}"
                        black_eval = f"M{evaluation['value']}"
                    self.eval_text.setText(f"White: {white_eval} | Black: {black_eval}")
                
                # Update eval bar
                self.eval_bar.set_eval(white_eval, black_eval)
                
            except Exception as e:
                print(f"Error during Stockfish evaluation: {e}")
                self.eval_text.setText("White: 0.00 | Black: 0.00")
                self.eval_bar.set_eval(0.0, 0.0)

    def make_stockfish_move(self):
        with BOARD_LOCK:
            if board.turn != chess.BLACK:
                return

            stockfish.set_fen_position(board.fen())
            best_move = stockfish.get_best_move()
            
            if best_move:
                move = chess.Move.from_uci(best_move)
                if move in board.legal_moves:
                    board.push(move)
                    self.update_board()
                    self.analyze_position()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Opening Trainer")
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Set up layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create chess board
        self.chess_board = ChessBoard(self)
        layout.addWidget(self.chess_board)
        
        # Create info panel
        info_panel = QWidget()
        info_layout = QHBoxLayout(info_panel)
        info_layout.setContentsMargins(10, 5, 10, 5)
        
        # Opening selector
        self.opening_selector = QComboBox()
        self.opening_selector.addItems([opening for opening in OPENING_MOVES.keys()])
        # Set the current item to match the SELECTED_OPENING
        self.opening_selector.setCurrentText(SELECTED_OPENING)
        # Block signals during initialization to prevent triggering change_opening
        self.opening_selector.blockSignals(True)
        self.opening_selector.setCurrentText(SELECTED_OPENING)
        self.opening_selector.blockSignals(False)
        self.opening_selector.currentTextChanged.connect(self.change_opening)
        info_layout.addWidget(QLabel("Opening:"))
        info_layout.addWidget(self.opening_selector)

        # Line selector
        self.line_selector = QComboBox()
        self.update_line_selector()
        self.line_selector.currentTextChanged.connect(self.change_line)
        info_layout.addWidget(QLabel("Line:"))
        info_layout.addWidget(self.line_selector)

        # Reset button
        reset_button = QPushButton("Reset Position")
        reset_button.clicked.connect(self.reset_position)
        info_layout.addWidget(reset_button)
        
        layout.addWidget(info_panel)
        
        # Adjust size based on content
        self.adjustSize()

    def change_opening(self, opening_name):
        global SELECTED_OPENING, OPENING_MOVES, SELECTED_LINE, board
        try:
            # Update the global opening name first
            SELECTED_OPENING = opening_name
            # Force the combobox to display the correct opening
            if self.opening_selector.currentText() != opening_name:
                self.opening_selector.blockSignals(True)
                self.opening_selector.setCurrentText(opening_name)
                self.opening_selector.blockSignals(False)
                
            # Force update the line selector with the new opening
            self.line_selector.clear()
            if opening_name in OPENING_MOVES:
                self.line_selector.addItems([line['name'] for line in OPENING_MOVES[opening_name]])
                SELECTED_LINE = OPENING_MOVES[opening_name][0]
                self.line_selector.setCurrentText(SELECTED_LINE['name'])
            
            # Reset the board and update the UI
            board = chess.Board()
            self.chess_board.opening_index = 0
            self.chess_board.in_opening_phase = True
            self.chess_board.update_board()
            self.chess_board.analyze_position()
        except Exception as e:
            print(f"Error changing opening: {e}")
            # Revert to previous opening if there's an error
            self.opening_selector.setCurrentText(SELECTED_OPENING)

    def change_line(self, line_name):
        global SELECTED_LINE, OPENING_MOVES, board
        try:
            # Find and set the new line
            SELECTED_LINE = next(line for line in OPENING_MOVES[SELECTED_OPENING] if line['name'] == line_name)
            # Reset the board and update the UI
            board = chess.Board()
            self.chess_board.opening_index = 0
            self.chess_board.in_opening_phase = True
            self.chess_board.update_board()
            self.chess_board.analyze_position()
        except Exception as e:
            print(f"Error changing line: {e}")
            # Revert to previous line if there's an error
            self.line_selector.setCurrentText(SELECTED_LINE['name'])

    def update_line_selector(self):
        try:
            self.line_selector.clear()
            if SELECTED_OPENING in OPENING_MOVES:
                self.line_selector.addItems([line['name'] for line in OPENING_MOVES[SELECTED_OPENING]])
                # Ensure the current line is selected
                if SELECTED_LINE:
                    self.line_selector.setCurrentText(SELECTED_LINE['name'])
        except Exception as e:
            print(f"Error updating line selector: {e}")

    def reset_position(self):
        try:
            global board
            board = chess.Board()
            self.chess_board.opening_index = 0
            self.chess_board.in_opening_phase = True
            self.chess_board.update_board()
            self.chess_board.analyze_position()
        except Exception as e:
            print(f"Error resetting position: {e}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
