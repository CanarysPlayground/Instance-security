import java.io.*;
import java.sql.*;
import java.util.logging.Logger;
import javax.servlet.http.*;

public class VulnerableServlet extends HttpServlet {
    private static final String DB_PASSWORD = "admin123"; // Hardcoded credential
    private static final Logger LOGGER = Logger.getLogger("VulnerableLogger");

    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String userInput = request.getParameter("input"); // Unvalidated input
        
        // SQL Injection vulnerability
        try {
            Connection conn = DriverManager.getConnection("jdbc:mysql://localhost:3306/db", "root", DB_PASSWORD);
            Statement stmt = conn.createStatement();
            String query = "SELECT * FROM users WHERE name = '" + userInput + "'"; // Direct concatenation
            ResultSet rs = stmt.executeQuery(query);
            while (rs.next()) {
                response.getWriter().write(rs.getString("data"));
            }
        } catch (SQLException e) {
            LOGGER.severe("SQL Error: " + e.getMessage()); // Potential log injection
        }

        // Command Injection vulnerability
        String cmd = "ls " + userInput; // Unsafe command construction
        try {
            Process proc = Runtime.getRuntime().exec(cmd); // Executing untrusted input
            BufferedReader reader = new BufferedReader(new InputStreamReader(proc.getInputStream()));
            String line;
            while ((line = reader.readLine()) != null) {
                response.getWriter().write(line);
            }
        } catch (Exception e) {
            response.getWriter().write("Exec failed");
        }

        // Unsafe deserialization
        try {
            FileInputStream fis = new FileInputStream("data.ser");
            ObjectInputStream ois = new ObjectInputStream(fis); // No validation
            Object obj = ois.readObject(); // Potential arbitrary code execution
            response.getWriter().write(obj.toString());
        } catch (Exception e) {
            LOGGER.info("Deserialization error: " + e); // Unchecked exception logging
        }

        // Hardcoded sensitive data exposure
        String secretKey = "SUPER_SECRET_KEY_123"; // Exposed secret
        response.getWriter().write("Key: " + secretKey);

        // XSS vulnerability
        response.setContentType("text/html");
        response.getWriter().write("<h1>Welcome " + userInput + "</h1>"); // No sanitization
    }

    // Insecure random number generation
    public int generateToken() {
        return (int) (Math.random() * 1000); // Weak randomness
    }
}
