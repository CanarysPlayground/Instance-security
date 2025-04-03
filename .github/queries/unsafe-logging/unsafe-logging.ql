/**
 * @name Unsafe logging of sensitive data
 * @description Detects logging of potentially sensitive data without sanitization.
 * @kind problem
 * @problem.severity warning
 * @id java/unsafe-logging
 * @tags security
 */

import java
import DataFlow::PathGraph  // For DataFlow::PathNode and data flow analysis
import semmle.code.java.dataflow.DataFlow  // For DataFlow::Node

// Define a sink as a logging method (e.g., SLF4J's logger.info)
class LoggingSink extends DataFlow::Node {
  LoggingSink() {
    exists(MethodAccess ma |
      ma.getMethod().hasName("info") and
      ma.getMethod().getDeclaringType().hasQualifiedName("org.slf4j", "Logger") and
      this.asExpr() = ma.getArgument(0)
    )
  }
}

// Define a source as a potentially sensitive input (e.g., a method parameter)
class SensitiveSource extends DataFlow::Node {
  SensitiveSource() {
    this.asParameter().getType() instanceof TypeString and
    this.asParameter().getName().toLowerCase().matches("%password%")
  }
}

from DataFlow::PathNode source, DataFlow::PathNode sink
where
  source.getNode() instanceof SensitiveSource and
  sink.getNode() instanceof LoggingSink and
  DataFlow::localFlow(source.getNode(), sink.getNode())
select sink.getNode(), source, sink, "Potentially unsafe logging of sensitive data from $@."
